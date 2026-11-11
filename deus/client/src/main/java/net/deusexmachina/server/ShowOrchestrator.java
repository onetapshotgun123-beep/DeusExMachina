package net.deusexmachina.server;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import net.deusexmachina.ShowConstants;
import net.deusexmachina.net.ShowBossPayload;
import net.deusexmachina.net.ShowStatePayload;
import net.deusexmachina.net.ShowStormPayload;
import net.deusexmachina.net.ShowStrikePayload;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.advancements.AdvancementHolder;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.particles.DustParticleOptions;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.effect.MobEffect;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.ai.attributes.AttributeInstance;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.storage.ServerLevelData;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.server.ServerStartingEvent;
import net.neoforged.neoforge.event.server.ServerStoppedEvent;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
import net.neoforged.neoforge.network.PacketDistributor;
import org.joml.Vector3f;

/**
 * Thin server-side orchestrator. Owns the show clock (advanced per server tick,
 * re-anchored by client heard-position reports), player freeze, and event-scoped
 * weather. All audio and visuals live in the client mod.
 */
public final class ShowOrchestrator {
    private static ShowOrchestrator current;

    private final MinecraftServer server;
    private int state = ShowConstants.STATE_IDLE;
    private long samples;
    private int loopMode;
    private boolean rainForced;
    private boolean dropFired;
    private int closingStartTick;
    private int tickCount;
    private boolean[] savedWeather;
    private int[] savedWeatherTimes;
    private boolean bossVisible;
    private String bossTarget = "";
    private int bossHp;
    private UUID bossUuid;
    private int bossLiveHp;
    private boolean bossPhase2;
    private static final java.util.List<Holder<MobEffect>> BOSS_BUFFS = java.util.List.of(
            MobEffects.MOVEMENT_SPEED, MobEffects.DAMAGE_RESISTANCE,
            MobEffects.DAMAGE_BOOST, MobEffects.REGENERATION);
    private static final ResourceLocation FREE_ADVANCEMENT =
            ResourceLocation.fromNamespaceAndPath("deusexmachina", "server_free");
    private static final String FREE_CRITERION = "granted";

    private final Map<UUID, double[]> frozen = new HashMap<>();

    // The storm and the boss's fall share one clock: waves start at the drop, and the bar's
    // target dying latches the finish so nothing re-ignites the show.
    private final Map<Integer, Strike> strikes = new HashMap<>();
    private final List<Strike> pendingStrikes = new ArrayList<>();
    private int nextStrikeId;
    private int stormWave;
    private int stormHitCount;
    private int nextStormTick = ShowConstants.STORM_FIRST_TICKS;
    // The lance volley keeps its own clock: it is aimed at bodies, so it is spent between waves.
    private int nextLanceTick = ShowConstants.LASER_FIRST_TICKS;
    private boolean bossDefeated;
    private int bossDeathTick;
    private boolean freeGranted;
    private int freeGrantedCount;

    private static final class Strike {
        final int id;
        final UUID player;
        final String name;
        final byte kind;
        final int warnTicks;
        final float radius;
        final float damage;
        final int debuffTicks;
        final boolean tracks;
        final ResourceKey<Level> dimension;
        double x;
        double y;
        double z;
        /** Volley lances keep a fixed offset from the body they track; everything else is centred. */
        double offsetX;
        double offsetZ;
        int age;
        int startTick;

        Strike(int id, ServerPlayer player, byte kind, int warnTicks, float radius,
               float damage, int debuffTicks, boolean tracks) {
            this.id = id;
            this.player = player.getUUID();
            this.name = player.getName().getString();
            this.kind = kind;
            this.warnTicks = warnTicks;
            this.radius = radius;
            this.damage = damage;
            this.debuffTicks = debuffTicks;
            this.tracks = tracks;
            this.dimension = player.level().dimension();
            this.x = player.getX();
            this.y = player.getY();
            this.z = player.getZ();
        }
    }

    private ShowOrchestrator(MinecraftServer server) {
        this.server = server;
    }

    public static void onServerStarting(ServerStartingEvent event) {
        current = new ShowOrchestrator(event.getServer());
    }

    public static void onServerStopped(ServerStoppedEvent event) {
        if (current != null) {
            current.unfreezeAll();
            current.restoreWeather();
            current = null;
        }
    }

    public static void onServerTick(ServerTickEvent.Post event) {
        if (current != null) {
            current.tick();
        }
    }

    public static void onPlayerLogin(PlayerEvent.PlayerLoggedInEvent event) {
        if (current != null && event.getEntity() instanceof ServerPlayer player) {
            current.recoverCrashFreeze(player);
            if (current.state == ShowConstants.STATE_PLAYING && !current.dropFired) {
                current.freeze(player);
            }
            current.sendTo(player, new ShowStatePayload(current.syncAction(), current.samples));
            if (current.bossVisible) {
                current.sendTo(player, current.bossPayload());
            }
        }
    }

    public static void onPlayerLogout(PlayerEvent.PlayerLoggedOutEvent event) {
        if (current != null && event.getEntity() instanceof ServerPlayer player) {
            current.unfreeze(player);
            if (player.getUUID().equals(current.bossUuid)) {
                clearBuffs(player);
            }
        }
    }

    /** Client reports the sample it is actually hearing; re-anchor the clock. */
    public static void reanchor(long heardSamples) {
        if (current != null && (current.state == ShowConstants.STATE_PLAYING || current.state == ShowConstants.STATE_PAUSED)) {
            current.samples = Math.max(0L, Math.min(ShowConstants.TOTAL_SAMPLES, heardSamples));
        }
    }

    /** The /deusex start <player> <hp> path: run the show with the RONOVA bar on that player. */
    public static int commandStart(ServerPlayer player, int hp) {
        if (current != null) {
            current.startWithBoss(player, hp);
        }
        return 1;
    }

    /** The /deusex reset path: drop everything at once and leave the world as if no show ran. */
    public static int commandReset() {
        if (current != null) {
            current.resetAll();
        }
        return 1;
    }

    public static int commandPhase2(CommandSourceStack source) {
        if (current == null || current.state != ShowConstants.STATE_PLAYING
                || !current.bossVisible || current.bossUuid == null || current.bossDefeated) {
            source.sendFailure(Component.literal("Start or resume a living boss event first."));
            return 0;
        }
        ServerPlayer player = current.server.getPlayerList().getPlayer(current.bossUuid);
        if (player == null || !player.isAlive()) {
            source.sendFailure(Component.literal("The boss must be alive and online."));
            return 0;
        }
        if (current.bossPhase2) {
            source.sendFailure(Component.literal("The event is already in phase 2."));
            return 0;
        }
        current.enterPhase2(player);
        current.applyBossBuffs();
        current.broadcast(current.bossPayload());
        source.sendSuccess(() -> Component.literal(
                "Phase 2 activated: faster storm combos, nine-lance volleys every 15 seconds. Boss health unchanged."), true);
        return 1;
    }

    private byte syncAction() {
        return switch (state) {
            case ShowConstants.STATE_PLAYING -> loopMode == 1 ? ShowConstants.ACT_SYNC_LOOP : ShowConstants.ACT_SYNC;
            case ShowConstants.STATE_PAUSED -> ShowConstants.ACT_PAUSE;
            case ShowConstants.STATE_CLOSING -> ShowConstants.ACT_CLOSING;
            default -> ShowConstants.ACT_STOP;
        };
    }

    private void tick() {
        tickCount++;
        pollCommand();
        mirrorScores();
        trackBossHealth();
        applyBossBuffs();
        blessUnmarked();

        // The bar flatlines for a moment after the boss falls, then the whole event shuts down.
        if (bossDefeated && state != ShowConstants.STATE_IDLE && state != ShowConstants.STATE_CLOSING
                && tickCount - bossDeathTick >= ShowConstants.BOSS_DEATH_LINGER) {
            finishDefeat();
            return;
        }

        if (state == ShowConstants.STATE_PLAYING) {
            samples += ShowConstants.SAMPLES_PER_TICK;
            long tickPos = ShowConstants.samplesToTicks(samples);
            scheduleStorms(tickPos);
            scheduleLances(tickPos);
            tickStrikes();
            if (!rainForced && tickPos >= ShowConstants.RAIN_TICKS) {
                forceRain();
            }
            if (!dropFired && tickPos >= ShowConstants.DROP_TICKS) {
                dropFired = true;
                unfreezeAll();
            }
            if (samples >= ShowConstants.TOTAL_SAMPLES) {
                if (loopMode == 1) {
                    samples = 0L;
                    nextStormTick = ShowConstants.STORM_FIRST_TICKS;
                    nextLanceTick = ShowConstants.LASER_FIRST_TICKS;
                    cancelStrikes();
                    broadcast(new ShowStatePayload(ShowConstants.ACT_START_LOOP, samples));
                } else {
                    beginClosing();
                }
            }
        } else if (state == ShowConstants.STATE_CLOSING) {
            if (tickCount - closingStartTick >= ShowConstants.CLOSING_TICKS) {
                state = ShowConstants.STATE_IDLE;
                samples = 0L;
                broadcast(new ShowStatePayload(ShowConstants.ACT_STOP, 0L));
            }
        }
    }

    private void pollCommand() {
        var scoreboard = server.getScoreboard();
        var objective = scoreboard.getObjective("deusex");
        if (objective == null) {
            return;
        }
        var cmd = scoreboard.getOrCreatePlayerScore(net.minecraft.world.scores.ScoreHolder.forNameOnly("#cmd"), objective);
        int value = cmd.get();
        if (value == 0) {
            return;
        }
        cmd.set(0);
        switch (value) {
            case 1 -> start(false);
            case 2 -> pause();
            case 3 -> resume();
            case 4 -> stop();
            case 5 -> toggleLoop();
            default -> { }
        }
    }

    private void mirrorScores() {
        var scoreboard = server.getScoreboard();
        var objective = scoreboard.getObjective("deusex");
        if (objective == null) {
            return;
        }
        scoreboard.getOrCreatePlayerScore(net.minecraft.world.scores.ScoreHolder.forNameOnly("#state"), objective).set(state);
        scoreboard.getOrCreatePlayerScore(net.minecraft.world.scores.ScoreHolder.forNameOnly("#pos"), objective).set((int) ShowConstants.samplesToTicks(samples));
        scoreboard.getOrCreatePlayerScore(net.minecraft.world.scores.ScoreHolder.forNameOnly("#loop"), objective).set(loopMode);
        scoreboard.getOrCreatePlayerScore(net.minecraft.world.scores.ScoreHolder.forNameOnly("#dead"), objective).set(bossDefeated ? 1 : 0);
        scoreboard.getOrCreatePlayerScore(net.minecraft.world.scores.ScoreHolder.forNameOnly("#free"), objective).set(freeGrantedCount);
        scoreboard.getOrCreatePlayerScore(net.minecraft.world.scores.ScoreHolder.forNameOnly("#wave"), objective).set(stormWave);
        scoreboard.getOrCreatePlayerScore(net.minecraft.world.scores.ScoreHolder.forNameOnly("#hits"), objective).set(stormHitCount);
        scoreboard.getOrCreatePlayerScore(net.minecraft.world.scores.ScoreHolder.forNameOnly("#bolt"), objective).set(strikes.size());
    }

    private void startWithBoss(ServerPlayer player, int hp) {
        start(false);
        bossVisible = true;
        bossTarget = player.getGameProfile().getName();
        bossHp = hp;
        bossUuid = player.getUUID();
        bossLiveHp = hp;
        bossPhase2 = false;
        broadcast(bossPayload());
    }

    private ShowBossPayload bossPayload() {
        return new ShowBossPayload(bossVisible, bossTarget, bossLiveHp, bossPhase2);
    }

    private void enterPhase2(ServerPlayer player) {
        bossPhase2 = true;
        int position = (int) ShowConstants.samplesToTicks(samples);
        nextStormTick = Math.min(nextStormTick, Math.max(ShowConstants.STORM_FIRST_TICKS,
                position + ShowConstants.STORM_PHASE2_PERIOD_TICKS));
        nextLanceTick = Math.max(ShowConstants.LASER_FIRST_TICKS,
                position + ShowConstants.LASER_VOLLEY_P2_PERIOD_TICKS);
        dropAmbient(player, MobEffects.DAMAGE_RESISTANCE);
    }

    /** The bar mirrors the target's live health as a fraction of the configured max; death empties it. */
    private void trackBossHealth() {
        if (!bossVisible || bossUuid == null) {
            return;
        }
        ServerPlayer player = server.getPlayerList().getPlayer(bossUuid);
        if (player == null) {
            return;
        }
        boolean wasPhase2 = bossPhase2;
        int live;
        if (bossDefeated) {
            // Once the seal breaks the bar stays flat even if the player respawns: the show is over.
            live = 0;
        } else {
            live = player.isDeadOrDying() ? 0 : Math.round(bossHp * player.getHealth() / player.getMaxHealth());
            live = Math.max(0, Math.min(bossHp, live));
            if (live == 0) {
                bossPhase2 = false;
            } else if (live <= ShowConstants.BOSS_PHASE2_HP) {
                bossPhase2 = true;
            }
            if (wasPhase2 != bossPhase2) {
                // A tier change must not leave the other tier's ambient effects ticking down on the player.
                if (bossPhase2) {
                    enterPhase2(player);
                } else {
                    dropAmbient(player, MobEffects.DAMAGE_BOOST);
                    dropAmbient(player, MobEffects.REGENERATION);
                }
            }
            if (live == 0) {
                bossDefeated = true;
                bossDeathTick = tickCount;
                // The seal's storm dies with its bearer; nothing else may land after this.
                cancelStrikes();
                message("RONOVA has fallen. The show is ending...");
            }
        }
        if (live != bossLiveHp || wasPhase2 != bossPhase2) {
            bossLiveHp = live;
            broadcast(bossPayload());
        }
    }

    /**
     * The bar lends its bearer strength: a steady march while whole, and a molten surge once the
     * seal breaks at half health. Ambient marks them as ours so clearing a bar never strips
     * effects from anything else.
     */
    private void applyBossBuffs() {
        if (!bossVisible || bossUuid == null) {
            return;
        }
        ServerPlayer player = server.getPlayerList().getPlayer(bossUuid);
        if (player == null || player.isDeadOrDying() || bossDefeated) {
            return;
        }
        if (bossPhase2) {
            buff(player, MobEffects.MOVEMENT_SPEED, 1);
            buff(player, MobEffects.DAMAGE_BOOST, 0);
            buff(player, MobEffects.REGENERATION, 0);
        } else {
            buff(player, MobEffects.MOVEMENT_SPEED, 0);
            buff(player, MobEffects.DAMAGE_RESISTANCE, 0);
        }
    }

    /**
     * Everyone the bar does not belong to is blessed for as long as the show runs: resistance and
     * regeneration keep them on their feet through the seal's storm. Only our ambient copies are
     * refreshed, so a player's own potions and beacons are never overwritten.
     */
    private void blessUnmarked() {
        if (state != ShowConstants.STATE_PLAYING && state != ShowConstants.STATE_PAUSED) {
            return;
        }
        for (ServerPlayer player : server.getPlayerList().getPlayers()) {
            if (!player.isAlive() || player.isSpectator() || player.isCreative()
                    || (bossUuid != null && player.getUUID().equals(bossUuid))) {
                continue;
            }
            buff(player, MobEffects.DAMAGE_RESISTANCE, 0);
            buff(player, MobEffects.REGENERATION, 0);
        }
    }

    private void clearBlessing() {
        for (ServerPlayer player : server.getPlayerList().getPlayers()) {
            if (bossUuid != null && player.getUUID().equals(bossUuid)) {
                continue;
            }
            dropAmbient(player, MobEffects.DAMAGE_RESISTANCE);
            dropAmbient(player, MobEffects.REGENERATION);
        }
    }

    private static void buff(ServerPlayer player, Holder<MobEffect> effect, int amplifier) {
        MobEffectInstance active = player.getEffect(effect);
        if (active != null && active.isAmbient() && active.getAmplifier() == amplifier
                && active.getDuration() > 20) {
            return;
        }
        player.addEffect(new MobEffectInstance(effect, 40, amplifier, true, true, true));
    }

    private static void dropAmbient(ServerPlayer player, Holder<MobEffect> effect) {
        MobEffectInstance active = player.getEffect(effect);
        if (active != null && active.isAmbient()) {
            player.removeEffect(effect);
        }
    }

    private static void clearBuffs(ServerPlayer player) {
        for (Holder<MobEffect> effect : BOSS_BUFFS) {
            dropAmbient(player, effect);
        }
    }

    private void clearBossBuffs() {
        if (bossUuid != null) {
            ServerPlayer player = server.getPlayerList().getPlayer(bossUuid);
            if (player != null) {
                clearBuffs(player);
            }
        }
        bossPhase2 = false;
    }

    private void start(boolean loop) {
        if (state == ShowConstants.STATE_PLAYING || state == ShowConstants.STATE_PAUSED) {
            halt();
        }
        state = ShowConstants.STATE_PLAYING;
        samples = 0L;
        dropFired = loop;
        rainForced = loop;
        bossDefeated = false;
        bossDeathTick = 0;
        freeGranted = false;
        freeGrantedCount = 0;
        stormWave = 0;
        stormHitCount = 0;
        nextStormTick = ShowConstants.STORM_FIRST_TICKS;
        nextLanceTick = ShowConstants.LASER_FIRST_TICKS;
        cancelStrikes();
        if (!loop) {
            for (ServerPlayer player : server.getPlayerList().getPlayers()) {
                freeze(player);
            }
        }
        broadcast(new ShowStatePayload(loop ? ShowConstants.ACT_START_LOOP : ShowConstants.ACT_START, samples));
        message(loop ? "Deus Ex Machina: replaying." : "Deus Ex Machina: show started.");
    }

    private void pause() {
        if (state != ShowConstants.STATE_PLAYING) {
            return;
        }
        state = ShowConstants.STATE_PAUSED;
        broadcast(new ShowStatePayload(ShowConstants.ACT_PAUSE, samples));
    }

    private void resume() {
        if (state != ShowConstants.STATE_PAUSED) {
            return;
        }
        state = ShowConstants.STATE_PLAYING;
        broadcast(new ShowStatePayload(ShowConstants.ACT_SYNC, samples));
    }

    private void stop() {
        if (state == ShowConstants.STATE_IDLE) {
            return;
        }
        halt();
        beginClosing();
    }

    private void halt() {
        state = ShowConstants.STATE_IDLE;
        samples = 0L;
        dropFired = false;
        clearBossBuffs();
        clearBlessing();
        bossVisible = false;
        bossUuid = null;
        bossLiveHp = 0;
        cancelStrikes();
        broadcast(new ShowBossPayload(false, "", 0, false));
        unfreezeAll();
        restoreWeather();
    }

    /**
     * A hard reset: stop the clock, drop the bar, the storm and every latch, put the weather back,
     * and zero the mirrored scores so the next start begins from a clean sheet. Player health,
     * items and already-earned advancements are left alone.
     */
    private void resetAll() {
        halt();
        bossDefeated = false;
        bossDeathTick = 0;
        freeGranted = false;
        freeGrantedCount = 0;
        stormWave = 0;
        stormHitCount = 0;
        nextStormTick = ShowConstants.STORM_FIRST_TICKS;
        nextLanceTick = ShowConstants.LASER_FIRST_TICKS;
        bossHp = 0;
        bossTarget = "";
        bossPhase2 = false;
        dropFired = false;
        rainForced = false;
        loopMode = 0;
        closingStartTick = tickCount;
        pendingStrikes.clear();
        broadcast(new ShowStatePayload(ShowConstants.ACT_STOP, 0L));
        mirrorScores();
        message("Deus Ex Machina: event reset.");
    }

    private void beginClosing() {
        state = ShowConstants.STATE_CLOSING;
        closingStartTick = tickCount;
        clearBossBuffs();
        clearBlessing();
        bossVisible = false;
        bossUuid = null;
        bossLiveHp = 0;
        cancelStrikes();
        broadcast(new ShowBossPayload(false, "", 0, false));
        unfreezeAll();
        restoreWeather();
        broadcast(new ShowStatePayload(ShowConstants.ACT_CLOSING, samples));
    }

    private void toggleLoop() {
        loopMode = loopMode == 1 ? 0 : 1;
        message(loopMode == 1 ? "Deus Ex Machina: loop ON." : "Deus Ex Machina: loop OFF.");
    }

    /**
     * The seal's arsenal, in the order the sky spends it. The first two waves are plain bolts so a
     * player learns the mark before anything else lands; the rest rotate through the binding grasp,
     * the blood siphon and the fragmentation barrage, with bolts between them so the storm never
     * stops being about lightning. The lance is absent on purpose: it fires as a formation volley
     * on its own clock, and a second, single copy in the rotation would read as a stray beam.
     */
    private static final byte[] WAVE_KINDS = {
            ShowConstants.STRIKE_BOLT, ShowConstants.STRIKE_BOLT,
            ShowConstants.STRIKE_VORTEX, ShowConstants.STRIKE_GRASP,
            ShowConstants.STRIKE_BARRAGE, ShowConstants.STRIKE_RUPTURE,
            ShowConstants.STRIKE_SIPHON, ShowConstants.STRIKE_BOLT};

    private static byte comboKind(byte kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_BOLT, ShowConstants.STRIKE_RUPTURE -> ShowConstants.STRIKE_SIPHON;
            case ShowConstants.STRIKE_GRASP, ShowConstants.STRIKE_BARRAGE -> ShowConstants.STRIKE_RUPTURE;
            default -> ShowConstants.STRIKE_BOLT;
        };
    }

    /**
     * One wave per period, each non-boss player marked with their own strike. The boss is never
     * marked: the storm is what the seal throws at the server, not at its bearer. Once the bar's
     * seal breaks the sky answers on a much shorter clock.
     */
    private void scheduleStorms(long tickPos) {
        if (bossDefeated || tickPos < ShowConstants.STORM_FIRST_TICKS || tickPos < nextStormTick) {
            return;
        }
        int period = bossPhase2 ? ShowConstants.STORM_PHASE2_PERIOD_TICKS
                : ShowConstants.STORM_PERIOD_TICKS;
        int rest = bossPhase2 ? ShowConstants.STORM_PHASE2_REST_TICKS
                : ShowConstants.STORM_REST_TICKS;
        int gap = period;
        if ((stormWave + 1) % ShowConstants.STORM_VOLLEY == 0) {
            // The seal exhausts a volley, then the sky holds its breath.
            gap += rest;
        }
        nextStormTick = (int) tickPos + gap;
        stormWave++;
        byte kind = WAVE_KINDS[(stormWave - 1) % WAVE_KINDS.length];
        byte followupKind = bossPhase2 || stormWave > 2 ? comboKind(kind) : (byte) -1;
        List<ServerPlayer> marked = new ArrayList<>();
        for (ServerPlayer player : server.getPlayerList().getPlayers()) {
            if (strikeable(player)) {
                marked.add(player);
            }
        }
        broadcast(new ShowStormPayload(stormWave, marked.size(), bossVisible ? bossTarget : "",
                kind, followupKind));
        for (ServerPlayer player : marked) {
            Strike strike = new Strike(++nextStrikeId, player, kind, warnTicks(kind),
                    radius(kind), damage(kind), debuffTicks(kind), true);
            strikes.put(strike.id, strike);
            sendStrike(strike, ShowStrikePayload.TRACKING, strike.warnTicks);
            if (followupKind >= 0) {
                Strike followup = new Strike(++nextStrikeId, player, followupKind,
                        strike.warnTicks + ShowConstants.COMBO_DELAY_TICKS, radius(followupKind),
                        damage(followupKind), debuffTicks(followupKind), true);
                strikes.put(followup.id, followup);
                sendStrike(followup, ShowStrikePayload.TRACKING, followup.warnTicks);
            }
            float pitch = kind == ShowConstants.STRIKE_SIPHON ? 0.7F : 1.1F;
            player.level().playSound(null, player.getX(), player.getY(), player.getZ(),
                    kind == ShowConstants.STRIKE_GRASP ? SoundEvents.EVOKER_PREPARE_ATTACK
                            : SoundEvents.RESPAWN_ANCHOR_CHARGE,
                    SoundSource.WEATHER, 0.8F, pitch);
        }
    }

    private void scheduleLances(long tickPos) {
        if (bossDefeated || tickPos < ShowConstants.LASER_FIRST_TICKS || tickPos < nextLanceTick) {
            return;
        }
        int count = bossPhase2 ? ShowConstants.LASER_VOLLEY_P2 : ShowConstants.LASER_VOLLEY;
        float damage = bossPhase2 ? ShowConstants.LASER_VOLLEY_P2_DAMAGE
                : ShowConstants.LASER_VOLLEY_DAMAGE;
        nextLanceTick = (int) tickPos + (bossPhase2 ? ShowConstants.LASER_VOLLEY_P2_PERIOD_TICKS
                : ShowConstants.LASER_VOLLEY_PERIOD_TICKS);
        // Rotate each formation a little so consecutive volleys do not draw the same star.
        double base = nextStrikeId * 0.7;
        for (ServerPlayer player : server.getPlayerList().getPlayers()) {
            if (!strikeable(player)) {
                continue;
            }
            for (int i = 0; i < count; i++) {
                Strike strike = new Strike(++nextStrikeId, player, ShowConstants.STRIKE_LASER,
                        ShowConstants.LASER_WARN_TICKS, ShowConstants.LASER_RADIUS, damage, 0, true);
                if (i > 0) {
                    double angle = base + Math.PI * 2.0 * (i - 1) / (count - 1);
                    strike.offsetX = Math.cos(angle) * ShowConstants.LASER_VOLLEY_RING;
                    strike.offsetZ = Math.sin(angle) * ShowConstants.LASER_VOLLEY_RING;
                }
                strike.x = player.getX() + strike.offsetX;
                strike.y = player.getEyeY() - 0.15;
                strike.z = player.getZ() + strike.offsetZ;
                strikes.put(strike.id, strike);
                sendStrike(strike, ShowStrikePayload.TRACKING, strike.warnTicks);
            }
            // One charge for the whole formation: a sound per lance would stack into a scream.
            player.level().playSound(null, player.getX(), player.getY(), player.getZ(),
                    SoundEvents.RESPAWN_ANCHOR_CHARGE, SoundSource.WEATHER, 1.0F, 1.6F);
        }
    }

    private static int warnTicks(byte kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_GRASP -> ShowConstants.GRASP_WARN_TICKS;
            case ShowConstants.STRIKE_SIPHON -> ShowConstants.SIPHON_WARN_TICKS;
            case ShowConstants.STRIKE_LASER -> ShowConstants.LASER_WARN_TICKS;
            case ShowConstants.STRIKE_VORTEX -> ShowConstants.VORTEX_WARN_TICKS;
            case ShowConstants.STRIKE_RUPTURE -> ShowConstants.RUPTURE_WARN_TICKS;
            default -> ShowConstants.STORM_WARN_TICKS;
        };
    }

    private static float radius(byte kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_GRASP -> ShowConstants.GRASP_RADIUS;
            case ShowConstants.STRIKE_SIPHON -> ShowConstants.SIPHON_RADIUS;
            case ShowConstants.STRIKE_LASER -> ShowConstants.LASER_RADIUS;
            case ShowConstants.STRIKE_VORTEX -> ShowConstants.VORTEX_RADIUS;
            case ShowConstants.STRIKE_RUPTURE -> ShowConstants.RUPTURE_RADIUS;
            default -> ShowConstants.STORM_RADIUS;
        };
    }

    private static float damage(byte kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_GRASP -> ShowConstants.GRASP_DAMAGE;
            case ShowConstants.STRIKE_VORTEX -> ShowConstants.VORTEX_DAMAGE;
            case ShowConstants.STRIKE_RUPTURE -> ShowConstants.RUPTURE_DAMAGE;
            case ShowConstants.STRIKE_SIPHON -> 0.0F;
            case ShowConstants.STRIKE_BARRAGE -> 0.0F;
            default -> ShowConstants.STORM_DAMAGE;
        };
    }

    private static int debuffTicks(byte kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_GRASP -> ShowConstants.GRASP_DEBUFF_TICKS;
            case ShowConstants.STRIKE_BARRAGE -> ShowConstants.STORM_DEBUFF_TICKS / 2;
            // The lance pays in pure damage; it leaves no mark behind to fight through.
            case ShowConstants.STRIKE_LASER, ShowConstants.STRIKE_VORTEX,
                    ShowConstants.STRIKE_RUPTURE -> 0;
            default -> ShowConstants.STORM_DEBUFF_TICKS;
        };
    }

    /** Everything the storm may hit: alive, playing, and never the bar's bearer. */
    private boolean strikeable(ServerPlayer player) {
        return player.isAlive() && !player.isSpectator() && !player.isCreative()
                && (bossUuid == null || !player.getUUID().equals(bossUuid));
    }

    private void tickStrikes() {
        if (strikes.isEmpty()) {
            return;
        }
        List<Strike> landed = new ArrayList<>();
        Iterator<Strike> it = strikes.values().iterator();
        while (it.hasNext()) {
            Strike strike = it.next();
            if (tickCount < strike.startTick) {
                continue;
            }
            ServerPlayer target = server.getPlayerList().getPlayer(strike.player);
            if (strike.tracks && (target == null || !target.level().dimension().equals(strike.dimension)
                    || !target.isAlive() || target.isSpectator())) {
                it.remove();
                sendStrike(strike, ShowStrikePayload.CANCELLED, 0);
                continue;
            }
            strike.age++;
            boolean tracking = strike.tracks
                    && strike.age < strike.warnTicks - ShowConstants.STORM_LOCK_TICKS;
            if (tracking) {
                // Volley lances hold their slot in the formation while the body moves under them.
                strike.x = target.getX() + strike.offsetX;
                // The lance is aimed at the chest; every ground attack marks the feet.
                strike.y = strike.kind == ShowConstants.STRIKE_LASER
                        ? target.getEyeY() - 0.15 : target.getY() + 0.05;
                strike.z = target.getZ() + strike.offsetZ;
            } else if (strike.tracks && strike.kind != ShowConstants.STRIKE_LASER
                    && strike.age == strike.warnTicks - ShowConstants.STORM_LOCK_TICKS) {
                // Locked: snap the mark to the ground under the last tracked spot and hold it there.
                ServerLevel level = server.getLevel(strike.dimension);
                if (level != null) {
                    strike.y = level.getHeight(Heightmap.Types.WORLD_SURFACE,
                            Mth.floor(strike.x), Mth.floor(strike.z));
                }
            }
            int left = strike.warnTicks - strike.age;
            if (left <= 0) {
                it.remove();
                landed.add(strike);
            } else {
                sendStrike(strike, tracking ? ShowStrikePayload.TRACKING : ShowStrikePayload.LOCKED, left);
                if (strike.age % 4 == 0) {
                    stormParticles(strike, !tracking);
                }
            }
        }
        // Aggregate simultaneous beams so vanilla hurt immunity cannot swallow the rest of a volley.
        Map<ServerPlayer, Float> lanceDamage = new HashMap<>();
        for (Strike strike : landed) {
            strikeImpact(strike, lanceDamage);
        }
        lanceDamage.forEach((player, total) -> {
            if (strikeable(player) && player.hurt(player.serverLevel().damageSources().magic(), total)) {
                stormHitCount++;
            }
        });
        if (!pendingStrikes.isEmpty()) {
            for (Strike shard : pendingStrikes) {
                strikes.put(shard.id, shard);
            }
            pendingStrikes.clear();
        }
    }

    private void strikeImpact(Strike strike, Map<ServerPlayer, Float> lanceDamage) {
        sendStrike(strike, ShowStrikePayload.IMPACT, 0);
        ServerLevel level = server.getLevel(strike.dimension);
        if (level == null) {
            return;
        }
        int impactY = level.getHeight(Heightmap.Types.WORLD_SURFACE,
                Mth.floor(strike.x), Mth.floor(strike.z));
        switch (strike.kind) {
            case ShowConstants.STRIKE_GRASP -> graspImpact(strike, level, impactY);
            case ShowConstants.STRIKE_SIPHON -> siphonImpact(strike, level, impactY);
            case ShowConstants.STRIKE_BARRAGE -> barrageImpact(strike, level, impactY);
            case ShowConstants.STRIKE_LASER -> laserImpact(strike, level, lanceDamage);
            case ShowConstants.STRIKE_VORTEX -> vortexImpact(strike, level, impactY);
            case ShowConstants.STRIKE_RUPTURE -> ruptureImpact(strike, level, impactY);
            default -> boltImpact(strike, level, impactY);
        }
    }

    /**
     * The bolt: thunder, sparks, and for anything still inside the mark the full storm bite. The
     * visible bolt itself is drawn by each client, so the seal's colour is the show's, not
     * vanilla's white.
     */
    private void boltImpact(Strike strike, ServerLevel level, int impactY) {
        level.sendParticles(ParticleTypes.EXPLOSION_EMITTER, strike.x, impactY + 0.2, strike.z, 1, 0, 0, 0, 0);
        level.sendParticles(ParticleTypes.ELECTRIC_SPARK, strike.x, impactY + 0.7, strike.z, 44,
                strike.radius * 0.7, 1.3, strike.radius * 0.7, 0.28);
        level.sendParticles(new DustParticleOptions(new Vector3f(1.0F, 0.34F, 0.2F), 1.7F),
                strike.x, impactY + 0.4, strike.z, 60, strike.radius, 0.7, strike.radius, 0.22);
        level.playSound(null, strike.x, impactY, strike.z,
                SoundEvents.LIGHTNING_BOLT_THUNDER, SoundSource.WEATHER, 2.0F, 1.0F);
        level.playSound(null, strike.x, impactY, strike.z,
                SoundEvents.LIGHTNING_BOLT_IMPACT, SoundSource.WEATHER, 1.6F, 1.0F);

        for (ServerPlayer player : victims(strike, level)) {
            player.hurt(level.damageSources().lightningBolt(), strike.damage);
            player.addEffect(new MobEffectInstance(MobEffects.WEAKNESS, strike.debuffTicks, 0));
            player.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN, strike.debuffTicks, 1));
            player.addEffect(new MobEffectInstance(MobEffects.BLINDNESS, strike.debuffTicks, 0));
            stormHitCount++;
        }
    }

    /**
     * The grasp: a wide binding circle that roots whoever is still standing on it. Slowness VII
     * leaves almost no walking speed, nausea ruins their aim, and the lingering weakness keeps the
     * fight tilted toward the seal's bearer.
     */
    private void graspImpact(Strike strike, ServerLevel level, int impactY) {
        level.sendParticles(new DustParticleOptions(new Vector3f(0.72F, 0.30F, 1.0F), 2.0F),
                strike.x, impactY + 0.3, strike.z, 90, strike.radius, 0.5, strike.radius, 0.05);
        level.sendParticles(ParticleTypes.ENCHANT, strike.x, impactY + 1.2, strike.z, 60,
                strike.radius, 1.6, strike.radius, 0.5);
        level.sendParticles(ParticleTypes.SOUL, strike.x, impactY + 0.6, strike.z, 30,
                strike.radius * 0.6, 0.8, strike.radius * 0.6, 0.02);
        level.playSound(null, strike.x, impactY, strike.z,
                SoundEvents.EVOKER_CAST_SPELL, SoundSource.WEATHER, 2.0F, 0.7F);
        level.playSound(null, strike.x, impactY, strike.z,
                SoundEvents.RESPAWN_ANCHOR_DEPLETE, SoundSource.WEATHER, 1.6F, 1.4F);

        for (ServerPlayer player : victims(strike, level)) {
            player.hurt(level.damageSources().magic(), strike.damage);
            player.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN,
                    strike.debuffTicks, 6));
            player.addEffect(new MobEffectInstance(MobEffects.CONFUSION, strike.debuffTicks, 0));
            player.addEffect(new MobEffectInstance(MobEffects.WEAKNESS, strike.debuffTicks, 0));
            stormHitCount++;
        }
    }

    /**
     * The blood rite: the seal drinks from everyone still inside the circle and pours the stolen
     * life into its bearer. The drain cannot kill, so a player is left on a sliver, not the death
     * screen.
     */
    private void siphonImpact(Strike strike, ServerLevel level, int impactY) {
        level.sendParticles(new DustParticleOptions(new Vector3f(1.0F, 0.08F, 0.06F), 1.8F),
                strike.x, impactY + 0.8, strike.z, 80, strike.radius * 0.5, 1.1, strike.radius * 0.5, 0.02);
        level.sendParticles(ParticleTypes.SOUL, strike.x, impactY + 1.0, strike.z, 40,
                strike.radius * 0.5, 1.0, strike.radius * 0.5, 0.15);
        level.playSound(null, strike.x, impactY, strike.z,
                SoundEvents.SOUL_ESCAPE, SoundSource.WEATHER, 2.0F, 0.6F);

        int drained = 0;
        for (ServerPlayer player : victims(strike, level)) {
            float take = Math.min(ShowConstants.SIPHON_DRAIN, player.getHealth() - 2.0F);
            if (take > 0.0F && player.hurt(level.damageSources().magic(), take)) {
                drained++;
            }
            player.addEffect(new MobEffectInstance(MobEffects.CONFUSION,
                    ShowConstants.STORM_DEBUFF_TICKS, 0));
            stormHitCount++;
        }
        ServerPlayer boss = bossUuid == null ? null : server.getPlayerList().getPlayer(bossUuid);
        if (boss != null && !boss.isDeadOrDying() && drained > 0) {
            boss.heal(ShowConstants.SIPHON_BOSS_HEAL * drained);
            level.sendParticles(ParticleTypes.HEART, boss.getX(), boss.getY() + 1.8, boss.getZ(),
                    Math.min(8, drained * 2), 0.6, 0.4, 0.6, 0.02);
        }
    }

    /**
     * The barrage: the parent mark bursts into a ring of smaller bolts a heartbeat apart, so the
     * safe spot keeps moving while the player is already reacting to the first one.
     */
    private void barrageImpact(Strike strike, ServerLevel level, int impactY) {
        level.sendParticles(ParticleTypes.EXPLOSION_EMITTER, strike.x, impactY + 0.2, strike.z, 1, 0, 0, 0, 0);
        level.sendParticles(new DustParticleOptions(new Vector3f(1.0F, 0.55F, 0.15F), 1.6F),
                strike.x, impactY + 0.4, strike.z, 50, strike.radius, 0.6, strike.radius, 0.18);
        level.playSound(null, strike.x, impactY, strike.z,
                SoundEvents.LIGHTNING_BOLT_IMPACT, SoundSource.WEATHER, 1.2F, 1.35F);

        ServerPlayer target = server.getPlayerList().getPlayer(strike.player);
        if (target == null) {
            return;
        }
        for (int i = 0; i < ShowConstants.BARRAGE_SHARDS; i++) {
            double angle = Math.PI * 2.0 * i / ShowConstants.BARRAGE_SHARDS + strike.id * 0.7;
            Strike shard = new Strike(++nextStrikeId, target, ShowConstants.STRIKE_BOLT,
                    ShowConstants.BARRAGE_SHARD_WARN_TICKS, ShowConstants.BARRAGE_SHARD_RADIUS,
                    ShowConstants.BARRAGE_SHARD_DAMAGE, ShowConstants.STORM_DEBUFF_TICKS / 2, false);
            shard.x = strike.x + Math.cos(angle) * 2.9;
            shard.z = strike.z + Math.sin(angle) * 2.9;
            shard.y = level.getHeight(Heightmap.Types.WORLD_SURFACE,
                    Mth.floor(shard.x), Mth.floor(shard.z));
            shard.startTick = tickCount + ShowConstants.BARRAGE_SHARD_DELAY * (i + 1);
            pendingStrikes.add(shard);
        }
    }

    private void vortexImpact(Strike strike, ServerLevel level, int impactY) {
        level.sendParticles(new DustParticleOptions(new Vector3f(1.0F, 0.08F, 0.58F), 1.8F),
                strike.x, impactY + 0.6, strike.z, 80, strike.radius * 0.7, 1.0, strike.radius * 0.7, 0.08);
        level.sendParticles(ParticleTypes.SOUL, strike.x, impactY + 0.8, strike.z,
                35, strike.radius * 0.5, 0.8, strike.radius * 0.5, 0.08);
        level.playSound(null, strike.x, impactY, strike.z,
                SoundEvents.RESPAWN_ANCHOR_DEPLETE, SoundSource.WEATHER, 1.6F, 0.6F);
        for (ServerPlayer player : victims(strike, level)) {
            if (player.hurt(level.damageSources().magic(), strike.damage)) {
                stormHitCount++;
            }
            double dx = strike.x - player.getX();
            double dz = strike.z - player.getZ();
            double distance = Math.sqrt(dx * dx + dz * dz);
            if (distance > 0.01) {
                double speed = Math.min(1.1, distance * 0.3);
                player.setDeltaMovement(dx / distance * speed,
                        Math.max(0.18, player.getDeltaMovement().y), dz / distance * speed);
                player.hurtMarked = true;
            }
        }
    }

    private void ruptureImpact(Strike strike, ServerLevel level, int impactY) {
        level.sendParticles(new DustParticleOptions(new Vector3f(1.0F, 0.40F, 0.04F), 2.0F),
                strike.x, impactY + 1.2, strike.z, 80, strike.radius * 0.6, 2.0, strike.radius * 0.6, 0.14);
        level.sendParticles(ParticleTypes.FLAME, strike.x, impactY + 0.5, strike.z,
                40, strike.radius * 0.6, 0.5, strike.radius * 0.6, 0.12);
        level.playSound(null, strike.x, impactY, strike.z,
                SoundEvents.GENERIC_EXPLODE.value(), SoundSource.WEATHER, 1.4F, 0.8F);
        for (ServerPlayer player : victims(strike, level)) {
            if (player.hurt(level.damageSources().magic(), strike.damage)) {
                stormHitCount++;
            }
            player.setDeltaMovement(player.getDeltaMovement().x, 0.8, player.getDeltaMovement().z);
            player.hurtMarked = true;
        }
    }

    private void laserImpact(Strike strike, ServerLevel level, Map<ServerPlayer, Float> lanceDamage) {
        double y = strike.y;
        level.sendParticles(ParticleTypes.EXPLOSION, strike.x, y, strike.z, 4, 0.35, 0.3, 0.35, 0.0);
        level.sendParticles(new DustParticleOptions(new Vector3f(1.0F, 0.38F, 0.10F), 1.5F),
                strike.x, y, strike.z, 70, 0.4, 0.4, 0.4, 0.08);
        level.sendParticles(ParticleTypes.ELECTRIC_SPARK, strike.x, y, strike.z, 50,
                0.5, 0.5, 0.5, 0.45);
        // Only the centre lance sounds; overlapping cues would multiply the volley volume.
        if (strike.offsetX == 0.0 && strike.offsetZ == 0.0) {
            level.playSound(null, strike.x, y, strike.z,
                    SoundEvents.BEACON_DEACTIVATE, SoundSource.WEATHER, 2.0F, 0.6F);
            level.playSound(null, strike.x, y, strike.z,
                    SoundEvents.LIGHTNING_BOLT_IMPACT, SoundSource.WEATHER, 1.4F, 1.5F);
        }

        for (ServerPlayer player : victims(strike, level)) {
            lanceDamage.merge(player, strike.damage, Float::sum);
        }
    }

    /** Players still inside a mark when it lands, in the same dimension and near its height. */
    private List<ServerPlayer> victims(Strike strike, ServerLevel level) {
        List<ServerPlayer> hit = new ArrayList<>();
        for (ServerPlayer player : server.getPlayerList().getPlayers()) {
            if (!strikeable(player) || !player.level().dimension().equals(strike.dimension)) {
                continue;
            }
            double dx = player.getX() - strike.x;
            double dz = player.getZ() - strike.z;
            double dy = player.getY() - strike.y;
            if (dx * dx + dz * dz <= strike.radius * strike.radius && Math.abs(dy) <= 4.0) {
                hit.add(player);
            }
        }
        return hit;
    }

    private void stormParticles(Strike strike, boolean locked) {
        ServerLevel level = server.getLevel(strike.dimension);
        if (level == null) {
            return;
        }
        Vector3f color = switch (strike.kind) {
            case ShowConstants.STRIKE_GRASP -> locked ? new Vector3f(0.78F, 0.20F, 1.0F)
                    : new Vector3f(0.78F, 0.72F, 1.0F);
            case ShowConstants.STRIKE_SIPHON -> locked ? new Vector3f(1.0F, 0.05F, 0.04F)
                    : new Vector3f(1.0F, 0.72F, 0.66F);
            case ShowConstants.STRIKE_BARRAGE -> locked ? new Vector3f(1.0F, 0.42F, 0.05F)
                    : new Vector3f(1.0F, 0.82F, 0.55F);
            case ShowConstants.STRIKE_VORTEX -> locked ? new Vector3f(1.0F, 0.08F, 0.58F)
                    : new Vector3f(1.0F, 0.62F, 0.86F);
            case ShowConstants.STRIKE_RUPTURE -> locked ? new Vector3f(1.0F, 0.40F, 0.04F)
                    : new Vector3f(1.0F, 0.82F, 0.52F);
            case ShowConstants.STRIKE_LASER -> locked ? new Vector3f(1.0F, 0.32F, 0.05F)
                    : new Vector3f(1.0F, 0.86F, 0.52F);
            default -> locked ? new Vector3f(1.0F, 0.16F, 0.12F)
                    : new Vector3f(0.96F, 0.9F, 1.0F);
        };
        DustParticleOptions dust = new DustParticleOptions(color, locked ? 1.4F : 1.1F);
        int points = locked ? 14 : 7;
        for (int i = 0; i < points; i++) {
            double angle = Math.PI * 2.0 * i / points + strike.age * 0.11;
            level.sendParticles(dust,
                    strike.x + Math.cos(angle) * strike.radius, strike.y + 0.12,
                    strike.z + Math.sin(angle) * strike.radius, 1, 0, 0, 0, 0);
        }
        // A slow rising spiral marks the column the attack will fall down.
        for (int i = 0; i < 3; i++) {
            double angle = strike.age * 0.35 + i * (Math.PI * 2.0 / 3.0);
            level.sendParticles(ParticleTypes.ELECTRIC_SPARK,
                    strike.x + Math.cos(angle) * 0.7, strike.y + 0.4 + i * 0.7,
                    strike.z + Math.sin(angle) * 0.7, 1, 0, 0.02, 0, 0.0);
        }
        if (locked) {
            level.sendParticles(ParticleTypes.ENCHANT, strike.x, strike.y + 1.0, strike.z,
                    4, 0.5, 0.6, 0.5, 0.4);
        }
    }

    private void sendStrike(Strike strike, byte phase, int ticksLeft) {
        // Kind and state share one byte: two bits of state, the kind above them (up to 63 kinds).
        broadcast(new ShowStrikePayload(strike.id, strike.x, strike.y, strike.z, ticksLeft,
                (byte) ((strike.kind << 2) | (phase & 0x3))));
    }

    private void cancelStrikes() {
        for (Strike strike : strikes.values()) {
            sendStrike(strike, ShowStrikePayload.CANCELLED, 0);
        }
        strikes.clear();
        pendingStrikes.clear();
    }

    /** The seal's reward: everyone still online gets the same advancement, once per victory. */
    private void grantFreeAdvancement() {
        if (freeGranted) {
            return;
        }
        freeGranted = true;
        AdvancementHolder holder = server.getAdvancements().get(FREE_ADVANCEMENT);
        if (holder == null) {
            return;
        }
        for (ServerPlayer player : server.getPlayerList().getPlayers()) {
            player.getAdvancements().award(holder, FREE_CRITERION);
            if (player.getAdvancements().getOrStartProgress(holder).isDone()) {
                freeGrantedCount++;
            }
        }
    }

    private void finishDefeat() {
        grantFreeAdvancement();
        message("The seal is broken. Server is finally free... at last.");
        beginClosing();
    }

    private void forceRain() {
        rainForced = true;
        ServerLevel level = server.overworld();
        ServerLevelData data = (ServerLevelData) level.getLevelData();
        savedWeather = new boolean[] { data.isRaining(), data.isThundering() };
        savedWeatherTimes = new int[] { data.getRainTime(), data.getThunderTime(), data.getClearWeatherTime() };
        level.setWeatherParameters(0, 1000000, true, false);
    }

    private void restoreWeather() {
        if (!rainForced) {
            return;
        }
        rainForced = false;
        if (savedWeather == null) {
            return;
        }
        ServerLevel level = server.overworld();
        ServerLevelData data = (ServerLevelData) level.getLevelData();
        data.setRaining(savedWeather[0]);
        data.setThundering(savedWeather[1]);
        data.setRainTime(savedWeatherTimes[0]);
        data.setThunderTime(savedWeatherTimes[1]);
        data.setClearWeatherTime(savedWeatherTimes[2]);
        savedWeather = null;
    }

    private void freeze(ServerPlayer player) {
        if (frozen.containsKey(player.getUUID())) {
            return;
        }
        double[] originals = new double[4];
        var gravity = player.getAttribute(Attributes.GRAVITY);
        originals[3] = gravity != null ? gravity.getBaseValue() : 0.08;
        if (gravity != null) {
            gravity.setBaseValue(0.0);
        }
        originals[0] = setZero(player, Attributes.MOVEMENT_SPEED);
        originals[1] = setZero(player, Attributes.FLYING_SPEED);
        originals[2] = setZero(player, Attributes.JUMP_STRENGTH);
        frozen.put(player.getUUID(), originals);
        CompoundTag tag = player.getPersistentData().getCompound(Player.PERSISTED_NBT_TAG);
        tag.putDouble("deusex_speed", originals[0]);
        tag.putDouble("deusex_fly", originals[1]);
        tag.putDouble("deusex_jump", originals[2]);
        tag.putDouble("deusex_gravity", originals[3]);
        tag.putBoolean("deusex_frozen", true);
        player.getPersistentData().put(Player.PERSISTED_NBT_TAG, tag);
    }

    private static double setZero(ServerPlayer player, net.minecraft.core.Holder<net.minecraft.world.entity.ai.attributes.Attribute> attribute) {
        AttributeInstance instance = player.getAttribute(attribute);
        if (instance == null) {
            return 0.0;
        }
        double original = instance.getBaseValue();
        instance.setBaseValue(0.0);
        return original;
    }

    private void unfreeze(ServerPlayer player) {
        double[] originals = frozen.remove(player.getUUID());
        CompoundTag tag = player.getPersistentData().getCompound(Player.PERSISTED_NBT_TAG);
        if (originals == null && tag.getBoolean("deusex_frozen")) {
            originals = new double[] { tag.getDouble("deusex_speed"), tag.getDouble("deusex_fly"), tag.getDouble("deusex_jump"), tag.contains("deusex_gravity") ? tag.getDouble("deusex_gravity") : 0.08 };
        }
        if (originals != null) {
            restore(player, Attributes.MOVEMENT_SPEED, originals[0]);
            restore(player, Attributes.FLYING_SPEED, originals[1]);
            restore(player, Attributes.JUMP_STRENGTH, originals[2]);
            restore(player, Attributes.GRAVITY, originals[3]);
        }
        tag.remove("deusex_frozen");
        tag.remove("deusex_speed");
        tag.remove("deusex_fly");
        tag.remove("deusex_jump");
        tag.remove("deusex_gravity");
        player.getPersistentData().put(Player.PERSISTED_NBT_TAG, tag);
    }

    private void recoverCrashFreeze(ServerPlayer player) {
        CompoundTag tag = player.getPersistentData().getCompound(Player.PERSISTED_NBT_TAG);
        if (tag.getBoolean("deusex_frozen")) {
            unfreeze(player);
        }
    }

    private static void restore(ServerPlayer player, net.minecraft.core.Holder<net.minecraft.world.entity.ai.attributes.Attribute> attribute, double value) {
        AttributeInstance instance = player.getAttribute(attribute);
        if (instance != null) {
            instance.setBaseValue(value);
        }
    }

    private void unfreezeAll() {
        for (ServerPlayer player : server.getPlayerList().getPlayers()) {
            unfreeze(player);
        }
        frozen.clear();
    }

    private void broadcast(CustomPacketPayload payload) {
        PacketDistributor.sendToAllPlayers(payload);
    }

    private void sendTo(ServerPlayer player, CustomPacketPayload payload) {
        PacketDistributor.sendToPlayer(player, payload);
    }

    private void message(String text) {
        server.getPlayerList().broadcastSystemMessage(Component.literal(text).withStyle(ChatFormatting.DARK_RED), false);
    }
}