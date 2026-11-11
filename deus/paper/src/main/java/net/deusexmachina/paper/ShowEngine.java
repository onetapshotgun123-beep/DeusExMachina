package net.deusexmachina.paper;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.HeightMap;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.SoundCategory;
import org.bukkit.World;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.advancement.Advancement;
import org.bukkit.advancement.AdvancementProgress;
import org.bukkit.boss.BarColor;
import org.bukkit.boss.BarFlag;
import org.bukkit.boss.BarStyle;
import org.bukkit.boss.BossBar;
import org.bukkit.command.CommandSender;
import org.bukkit.damage.DamageSource;
import org.bukkit.damage.DamageType;
import org.bukkit.entity.Player;
import org.bukkit.GameMode;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.util.Vector;

/**
 * The show's server brain, ported from the mod's ShowOrchestrator. Owns the tick clock, the
 * storm scheduler, every strike from warning to impact, the boss bar and its phase latch,
 * player freeze, weather and the victory advancement. Audio, screen and glow are driven from
 * here so all four halves land on the same tick.
 */
public final class ShowEngine {
    private static final DamageSource MAGIC = DamageSource.builder(DamageType.MAGIC).build();
    private static final DamageSource BOLT = DamageSource.builder(DamageType.LIGHTNING_BOLT).build();
    private static final PotionEffectType[] BOSS_BUFFS = {
            PotionEffectType.SPEED, PotionEffectType.RESISTANCE,
            PotionEffectType.STRENGTH, PotionEffectType.REGENERATION
    };

    /** One scheduled attack. Volley lances keep a fixed offset from the body they track. */
    public static final class Strike {
        public final int id;
        public final UUID player;
        public final byte kind;
        public final int warnTicks;
        public final float radius;
        public final float damage;
        public final int debuffTicks;
        public final boolean tracks;
        public final UUID worldId;
        public double x;
        public double y;
        public double z;
        public double offsetX;
        public double offsetZ;
        public int age;
        public int startTick;

        Strike(int id, Player player, byte kind, int warnTicks, float radius,
               float damage, int debuffTicks, boolean tracks, int tickCount) {
            this.id = id;
            this.player = player.getUniqueId();
            this.kind = kind;
            this.warnTicks = warnTicks;
            this.radius = radius;
            this.damage = damage;
            this.debuffTicks = debuffTicks;
            this.tracks = tracks;
            this.worldId = player.getWorld().getUID();
            Location at = player.getLocation();
            this.x = at.getX();
            this.y = at.getY();
            this.z = at.getZ();
            this.startTick = tickCount;
        }
    }

    private final DeusExPlugin plugin;
    private final NamespacedKey kFrozen;
    private final NamespacedKey kSpeed;
    private final NamespacedKey kFly;
    private final NamespacedKey kJump;
    private final NamespacedKey kGravity;

    private int state = ShowConstants.STATE_IDLE;
    private int musicTick;
    private int tickCount;
    private int loopMode;
    private boolean rainForced;
    private boolean dropFired;
    private int closingStartTick;

    private boolean bossVisible;
    private String bossTarget = "";
    private int bossHp;
    private UUID bossUuid;
    private int bossLiveHp;
    private boolean bossPhase2;
    private boolean bossDefeated;
    private int bossDeathTick;
    private boolean freeGranted;
    private int freeGrantedCount;
    private BossBar bar;

    private final Map<Integer, Strike> strikes = new LinkedHashMap<>();
    private final List<Strike> pendingStrikes = new ArrayList<>();
    private int nextStrikeId;
    private int stormWave;
    private int stormHitCount;
    private int nextStormTick = ShowConstants.STORM_FIRST_TICKS;
    private int nextLanceTick = ShowConstants.LASER_FIRST_TICKS;

    private final Map<UUID, double[]> frozen = new HashMap<>();
    private boolean[] savedWeather;
    private int[] savedWeatherTimes;

    public ShowEngine(DeusExPlugin plugin) {
        this.plugin = plugin;
        kFrozen = new NamespacedKey(plugin, "frozen");
        kSpeed = new NamespacedKey(plugin, "speed");
        kFly = new NamespacedKey(plugin, "fly");
        kJump = new NamespacedKey(plugin, "jump");
        kGravity = new NamespacedKey(plugin, "gravity");
    }

    public int state() {
        return state;
    }

    public boolean isBoss(Player player) {
        return bossVisible && bossUuid != null && bossUuid.equals(player.getUniqueId());
    }

    /** The strike hunting this player right now; a locked mark outranks a tracking one. */
    public Strike markOn(Player player) {
        Strike best = null;
        for (Strike strike : strikes.values()) {
            if (!strike.tracks || !strike.player.equals(player.getUniqueId())) {
                continue;
            }
            if (strike.age >= strike.warnTicks - ShowConstants.STORM_LOCK_TICKS) {
                return strike;
            }
            if (best == null) {
                best = strike;
            }
        }
        return best;
    }

    public void tick() {
        tickCount++;
        trackBossHealth();
        applyBossBuffs();
        blessUnmarked();
        plugin.glow().tick(this);

        // The bar flatlines for a moment after the boss falls, then the whole event shuts down.
        if (bossDefeated && state != ShowConstants.STATE_IDLE && state != ShowConstants.STATE_CLOSING
                && tickCount - bossDeathTick >= ShowConstants.BOSS_DEATH_LINGER) {
            finishDefeat();
        } else if (state == ShowConstants.STATE_PLAYING) {
            musicTick++;
            plugin.audio().tick(musicTick);
            scheduleStorms(musicTick);
            scheduleLances(musicTick);
            tickStrikes();
            if (!rainForced && musicTick >= ShowConstants.RAIN_TICKS) {
                forceRain();
            }
            if (!dropFired && musicTick >= ShowConstants.DROP_TICKS) {
                dropFired = true;
                unfreezeAll();
            }
            if (musicTick >= ShowAudio.TOTAL_TICKS) {
                if (loopMode == 1) {
                    musicTick = 0;
                    nextStormTick = ShowConstants.STORM_FIRST_TICKS;
                    nextLanceTick = ShowConstants.LASER_FIRST_TICKS;
                    cancelStrikes();
                    plugin.screen().begin();
                    plugin.audio().start();
                } else {
                    beginClosing();
                }
            }
        } else if (state == ShowConstants.STATE_CLOSING) {
            if (tickCount - closingStartTick >= ShowConstants.CLOSING_TICKS) {
                state = ShowConstants.STATE_IDLE;
                musicTick = 0;
            }
        }
        plugin.screen().tick(state, musicTick, tickCount);
    }

    // ------------------------------------------------------------------ commands

    public void startWithBoss(Player player, int hp) {
        start(false);
        bossVisible = true;
        bossTarget = player.getName();
        bossHp = hp;
        bossUuid = player.getUniqueId();
        bossLiveHp = hp;
        bossPhase2 = false;
        bar = Bukkit.createBossBar("§4RONOVA §8— §f" + bossTarget,
                BarColor.YELLOW, BarStyle.SEGMENTED_10);
        for (Player online : Bukkit.getOnlinePlayers()) {
            bar.addPlayer(online);
        }
        updateBar();
    }

    public void pause() {
        if (state != ShowConstants.STATE_PLAYING) {
            return;
        }
        state = ShowConstants.STATE_PAUSED;
        plugin.audio().pause();
    }

    public void resume() {
        if (state != ShowConstants.STATE_PAUSED) {
            return;
        }
        state = ShowConstants.STATE_PLAYING;
        plugin.audio().resume(musicTick);
    }

    public void stop() {
        if (state == ShowConstants.STATE_IDLE) {
            return;
        }
        beginClosing();
    }

    public void toggleLoop() {
        loopMode = loopMode == 1 ? 0 : 1;
        message(loopMode == 1 ? "Deus Ex Machina: loop ON." : "Deus Ex Machina: loop OFF.");
    }

    public boolean commandPhase2(CommandSender source) {
        if (state != ShowConstants.STATE_PLAYING || !bossVisible || bossUuid == null || bossDefeated) {
            source.sendMessage(Component.text("Start or resume a living boss event first.", NamedTextColor.RED));
            return false;
        }
        Player player = Bukkit.getPlayer(bossUuid);
        if (player == null || player.isDead()) {
            source.sendMessage(Component.text("The boss must be alive and online.", NamedTextColor.RED));
            return false;
        }
        if (bossPhase2) {
            source.sendMessage(Component.text("The event is already in phase 2.", NamedTextColor.RED));
            return false;
        }
        enterPhase2(player);
        applyBossBuffs();
        source.sendMessage(Component.text(
                "Phase 2 activated: faster storm combos, nine-lance volleys. Boss health unchanged.",
                NamedTextColor.GREEN));
        return true;
    }

    /** A hard reset: drop the bar, the storm and every latch; health, items and advancements stay. */
    public void resetAll() {
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
        pendingStrikes.clear();
        plugin.screen().clearAll();
        message("Deus Ex Machina: event reset.");
    }

    public void shutdown() {
        halt();
        plugin.screen().clearAll();
    }

    public List<String> status() {
        List<String> lines = new ArrayList<>();
        String stateName = switch (state) {
            case ShowConstants.STATE_PLAYING -> "PLAYING";
            case ShowConstants.STATE_PAUSED -> "PAUSED";
            case ShowConstants.STATE_CLOSING -> "CLOSING";
            default -> "IDLE";
        };
        lines.add("State: " + stateName + "  pos: " + musicTick + "t (" + musicTick / 20 + "s)  loop: " + loopMode);
        lines.add("Storm: wave " + stormWave + ", hits " + stormHitCount + ", active strikes " + strikes.size());
        if (bossVisible) {
            lines.add("Boss: " + bossTarget + "  hp " + bossLiveHp + "/" + bossHp
                    + (bossPhase2 ? "  PHASE 2" : "") + (bossDefeated ? "  DEFEATED" : ""));
        } else {
            lines.add("Boss: none");
        }
        lines.add("Free advancement granted: " + freeGrantedCount);
        lines.add("Pack: " + plugin.packServer().url());
        return lines;
    }

    // ------------------------------------------------------------------ lifecycle

    private void start(boolean loop) {
        if (state == ShowConstants.STATE_PLAYING || state == ShowConstants.STATE_PAUSED) {
            halt();
        }
        state = ShowConstants.STATE_PLAYING;
        musicTick = 0;
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
            for (Player player : Bukkit.getOnlinePlayers()) {
                freeze(player);
            }
        }
        plugin.screen().begin();
        plugin.audio().start();
        message(loop ? "Deus Ex Machina: replaying." : "Deus Ex Machina: show started.");
    }

    private void halt() {
        state = ShowConstants.STATE_IDLE;
        musicTick = 0;
        dropFired = false;
        clearBossBuffs();
        clearBlessing();
        hideBar();
        bossVisible = false;
        bossUuid = null;
        bossLiveHp = 0;
        cancelStrikes();
        unfreezeAll();
        restoreWeather();
        plugin.audio().stopAll();
    }

    private void beginClosing() {
        state = ShowConstants.STATE_CLOSING;
        closingStartTick = tickCount;
        clearBossBuffs();
        clearBlessing();
        hideBar();
        bossVisible = false;
        bossUuid = null;
        bossLiveHp = 0;
        cancelStrikes();
        unfreezeAll();
        restoreWeather();
        plugin.audio().stopAll();
        plugin.screen().beginClosing();
    }

    public void onJoin(Player player) {
        recoverCrashFreeze(player);
        if (state == ShowConstants.STATE_PLAYING && !dropFired) {
            freeze(player);
        }
        if (state == ShowConstants.STATE_PLAYING) {
            plugin.audio().catchUp(player, musicTick);
        }
        plugin.screen().syncPlayer(player, state, musicTick);
        if (bar != null) {
            bar.addPlayer(player);
        }
    }

    public void onQuit(Player player) {
        unfreeze(player);
        if (player.getUniqueId().equals(bossUuid)) {
            clearBuffs(player);
        }
        if (bar != null) {
            bar.removePlayer(player);
        }
    }

    // ------------------------------------------------------------------ boss

    /** The bar mirrors the target's live health as a fraction of the configured max. */
    private void trackBossHealth() {
        if (!bossVisible || bossUuid == null) {
            return;
        }
        Player player = Bukkit.getPlayer(bossUuid);
        if (player == null) {
            return;
        }
        boolean wasPhase2 = bossPhase2;
        int live;
        if (bossDefeated) {
            // Once the seal breaks the bar stays flat even if the player respawns.
            live = 0;
        } else {
            live = player.isDead() ? 0
                    : Math.round(bossHp * (float) player.getHealth() / (float) maxHealth(player));
            live = Math.max(0, Math.min(bossHp, live));
            if (live == 0) {
                bossPhase2 = false;
            } else if (live <= ShowConstants.BOSS_PHASE2_HP) {
                bossPhase2 = true;
            }
            if (wasPhase2 != bossPhase2) {
                if (bossPhase2) {
                    enterPhase2(player);
                } else {
                    dropAmbient(player, PotionEffectType.STRENGTH);
                    dropAmbient(player, PotionEffectType.REGENERATION);
                }
            }
            if (live == 0) {
                onBossDeath(player);
            }
        }
        if (live != bossLiveHp || wasPhase2 != bossPhase2) {
            bossLiveHp = live;
            updateBar();
        }
    }

    /** Also fired from PlayerDeathEvent so instant-respawn setups cannot skip the defeat. */
    public void onBossDeath(Player player) {
        if (!bossVisible || bossDefeated || bossUuid == null || !player.getUniqueId().equals(bossUuid)) {
            return;
        }
        bossDefeated = true;
        bossDeathTick = tickCount;
        cancelStrikes();
        message("RONOVA has fallen. The show is ending...");
    }

    private void enterPhase2(Player player) {
        bossPhase2 = true;
        nextStormTick = Math.min(nextStormTick, Math.max(ShowConstants.STORM_FIRST_TICKS,
                musicTick + ShowConstants.STORM_PHASE2_PERIOD_TICKS));
        nextLanceTick = Math.max(ShowConstants.LASER_FIRST_TICKS,
                musicTick + ShowConstants.LASER_VOLLEY_P2_PERIOD_TICKS);
        dropAmbient(player, PotionEffectType.RESISTANCE);
        updateBar();
        message("RONOVA's seal breaks — the storm quickens.");
    }

    private void updateBar() {
        if (bar == null) {
            return;
        }
        bar.setProgress(bossHp <= 0 ? 0.0 : Math.max(0.0, Math.min(1.0, bossLiveHp / (double) bossHp)));
        bar.setColor(bossPhase2 ? BarColor.RED : BarColor.YELLOW);
        if (bossPhase2) {
            bar.addFlag(BarFlag.DARKEN_SKY);
        } else {
            bar.removeFlag(BarFlag.DARKEN_SKY);
        }
    }

    private void hideBar() {
        if (bar != null) {
            bar.removeAll();
            bar = null;
        }
    }

    private static double maxHealth(Player player) {
        AttributeInstance instance = player.getAttribute(Attribute.MAX_HEALTH);
        return instance != null ? instance.getValue() : 20.0;
    }

    private void applyBossBuffs() {
        if (!bossVisible || bossUuid == null) {
            return;
        }
        Player player = Bukkit.getPlayer(bossUuid);
        if (player == null || player.isDead() || bossDefeated) {
            return;
        }
        if (bossPhase2) {
            buff(player, PotionEffectType.SPEED, 1);
            buff(player, PotionEffectType.STRENGTH, 0);
            buff(player, PotionEffectType.REGENERATION, 0);
        } else {
            buff(player, PotionEffectType.SPEED, 0);
            buff(player, PotionEffectType.RESISTANCE, 0);
        }
    }

    private void blessUnmarked() {
        if (state != ShowConstants.STATE_PLAYING && state != ShowConstants.STATE_PAUSED) {
            return;
        }
        for (Player player : Bukkit.getOnlinePlayers()) {
            if (player.isDead() || player.getGameMode() == GameMode.SPECTATOR
                    || player.getGameMode() == GameMode.CREATIVE
                    || (bossUuid != null && player.getUniqueId().equals(bossUuid))) {
                continue;
            }
            buff(player, PotionEffectType.RESISTANCE, 0);
            buff(player, PotionEffectType.REGENERATION, 0);
        }
    }

    private void clearBlessing() {
        for (Player player : Bukkit.getOnlinePlayers()) {
            if (bossUuid != null && player.getUniqueId().equals(bossUuid)) {
                continue;
            }
            dropAmbient(player, PotionEffectType.RESISTANCE);
            dropAmbient(player, PotionEffectType.REGENERATION);
        }
    }

    /** Only ambient copies are refreshed, so a player's own potions and beacons are never overwritten. */
    private static void buff(Player player, PotionEffectType effect, int amplifier) {
        PotionEffect active = player.getPotionEffect(effect);
        if (active != null && active.isAmbient() && active.getAmplifier() == amplifier
                && active.getDuration() > 20) {
            return;
        }
        player.addPotionEffect(new PotionEffect(effect, 40, amplifier, true, true, true));
    }

    private static void dropAmbient(Player player, PotionEffectType effect) {
        PotionEffect active = player.getPotionEffect(effect);
        if (active != null && active.isAmbient()) {
            player.removePotionEffect(effect);
        }
    }

    private static void clearBuffs(Player player) {
        for (PotionEffectType effect : BOSS_BUFFS) {
            dropAmbient(player, effect);
        }
    }

    private void clearBossBuffs() {
        if (bossUuid != null) {
            Player player = Bukkit.getPlayer(bossUuid);
            if (player != null) {
                clearBuffs(player);
            }
        }
        bossPhase2 = false;
    }

    // ------------------------------------------------------------------ storm scheduler

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

    private void scheduleStorms(int tickPos) {
        if (bossDefeated || tickPos < ShowConstants.STORM_FIRST_TICKS || tickPos < nextStormTick) {
            return;
        }
        int period = bossPhase2 ? ShowConstants.STORM_PHASE2_PERIOD_TICKS : ShowConstants.STORM_PERIOD_TICKS;
        int rest = bossPhase2 ? ShowConstants.STORM_PHASE2_REST_TICKS : ShowConstants.STORM_REST_TICKS;
        int gap = period;
        if ((stormWave + 1) % ShowConstants.STORM_VOLLEY == 0) {
            gap += rest;
        }
        nextStormTick = tickPos + gap;
        stormWave++;
        byte kind = WAVE_KINDS[(stormWave - 1) % WAVE_KINDS.length];
        byte followupKind = bossPhase2 || stormWave > 2 ? comboKind(kind) : (byte) -1;
        List<Player> marked = new ArrayList<>();
        for (Player player : Bukkit.getOnlinePlayers()) {
            if (strikeable(player)) {
                marked.add(player);
            }
        }
        message("Wave " + stormWave + ": " + kindName(kind) + " — " + marked.size() + " marked"
                + (followupKind >= 0 ? "  (combo: " + kindName(followupKind) + ")" : ""));
        for (Player player : marked) {
            Strike strike = new Strike(++nextStrikeId, player, kind, warnTicks(kind),
                    radius(kind), damage(kind), debuffTicks(kind), true, tickCount);
            strikes.put(strike.id, strike);
            if (followupKind >= 0) {
                Strike followup = new Strike(++nextStrikeId, player, followupKind,
                        strike.warnTicks + ShowConstants.COMBO_DELAY_TICKS, radius(followupKind),
                        damage(followupKind), debuffTicks(followupKind), true, tickCount);
                strikes.put(followup.id, followup);
            }
            float pitch = kind == ShowConstants.STRIKE_SIPHON ? 0.7F : 1.1F;
            player.getWorld().playSound(player.getLocation(),
                    kind == ShowConstants.STRIKE_GRASP ? Sound.ENTITY_EVOKER_PREPARE_ATTACK
                            : Sound.BLOCK_RESPAWN_ANCHOR_CHARGE,
                    SoundCategory.WEATHER, 0.8F, pitch);
        }
    }

    private void scheduleLances(int tickPos) {
        if (bossDefeated || tickPos < ShowConstants.LASER_FIRST_TICKS || tickPos < nextLanceTick) {
            return;
        }
        int count = bossPhase2 ? ShowConstants.LASER_VOLLEY_P2 : ShowConstants.LASER_VOLLEY;
        float damage = bossPhase2 ? ShowConstants.LASER_VOLLEY_P2_DAMAGE : ShowConstants.LASER_VOLLEY_DAMAGE;
        nextLanceTick = tickPos + (bossPhase2 ? ShowConstants.LASER_VOLLEY_P2_PERIOD_TICKS
                : ShowConstants.LASER_VOLLEY_PERIOD_TICKS);
        // Rotate each formation a little so consecutive volleys do not draw the same star.
        double base = nextStrikeId * 0.7;
        for (Player player : Bukkit.getOnlinePlayers()) {
            if (!strikeable(player)) {
                continue;
            }
            for (int i = 0; i < count; i++) {
                Strike strike = new Strike(++nextStrikeId, player, ShowConstants.STRIKE_LASER,
                        ShowConstants.LASER_WARN_TICKS, ShowConstants.LASER_RADIUS, damage, 0, true, tickCount);
                if (i > 0) {
                    double angle = base + Math.PI * 2.0 * (i - 1) / (count - 1);
                    strike.offsetX = Math.cos(angle) * ShowConstants.LASER_VOLLEY_RING;
                    strike.offsetZ = Math.sin(angle) * ShowConstants.LASER_VOLLEY_RING;
                }
                strike.x = player.getLocation().getX() + strike.offsetX;
                strike.y = player.getLocation().getY() + player.getEyeHeight() - 0.15;
                strike.z = player.getLocation().getZ() + strike.offsetZ;
                strikes.put(strike.id, strike);
            }
            // One charge for the whole formation: a sound per lance would stack into a scream.
            player.getWorld().playSound(player.getLocation(), Sound.BLOCK_RESPAWN_ANCHOR_CHARGE,
                    SoundCategory.WEATHER, 1.0F, 1.6F);
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
            case ShowConstants.STRIKE_SIPHON, ShowConstants.STRIKE_BARRAGE -> 0.0F;
            default -> ShowConstants.STORM_DAMAGE;
        };
    }

    private static int debuffTicks(byte kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_GRASP -> ShowConstants.GRASP_DEBUFF_TICKS;
            case ShowConstants.STRIKE_BARRAGE -> ShowConstants.STORM_DEBUFF_TICKS / 2;
            // The lance pays in pure damage; it leaves no mark behind to fight through.
            case ShowConstants.STRIKE_LASER, ShowConstants.STRIKE_VORTEX, ShowConstants.STRIKE_RUPTURE -> 0;
            default -> ShowConstants.STORM_DEBUFF_TICKS;
        };
    }

    private boolean strikeable(Player player) {
        return !player.isDead() && player.getGameMode() != GameMode.SPECTATOR
                && player.getGameMode() != GameMode.CREATIVE
                && (bossUuid == null || !player.getUniqueId().equals(bossUuid));
    }

    // ------------------------------------------------------------------ strike lifecycle

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
            Player target = Bukkit.getPlayer(strike.player);
            World world = Bukkit.getWorld(strike.worldId);
            if (strike.tracks && (world == null || target == null
                    || !target.getWorld().getUID().equals(strike.worldId)
                    || target.isDead() || target.getGameMode() == GameMode.SPECTATOR)) {
                it.remove();
                continue;
            }
            strike.age++;
            boolean tracking = strike.tracks
                    && strike.age < strike.warnTicks - ShowConstants.STORM_LOCK_TICKS;
            if (tracking) {
                // Volley lances hold their slot in the formation while the body moves under them.
                strike.x = target.getLocation().getX() + strike.offsetX;
                strike.y = strike.kind == ShowConstants.STRIKE_LASER
                        ? target.getLocation().getY() + target.getEyeHeight() - 0.15
                        : target.getLocation().getY() + 0.05;
                strike.z = target.getLocation().getZ() + strike.offsetZ;
            } else if (strike.tracks && strike.age == strike.warnTicks - ShowConstants.STORM_LOCK_TICKS) {
                if (strike.kind != ShowConstants.STRIKE_LASER && world != null) {
                    // Locked: snap the mark to the ground under the last tracked spot.
                    strike.y = world.getHighestBlockAt((int) Math.floor(strike.x),
                            (int) Math.floor(strike.z), HeightMap.WORLD_SURFACE).getY();
                }
                if (target != null) {
                    plugin.screen().callout(target, kindName(strike.kind) + " LOCKED",
                            calloutColor(strike.kind), tickCount);
                }
            }
            int left = strike.warnTicks - strike.age;
            if (left <= 0) {
                it.remove();
                landed.add(strike);
            } else if (strike.age % 4 == 0) {
                stormParticles(strike, !tracking);
            }
        }
        // Aggregate simultaneous beams so vanilla hurt immunity cannot swallow the rest of a volley.
        Map<Player, Float> lanceDamage = new HashMap<>();
        for (Strike strike : landed) {
            strikeImpact(strike, lanceDamage);
        }
        lanceDamage.forEach((player, total) -> {
            if (strikeable(player) && hurt(player, total, MAGIC)) {
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

    private void strikeImpact(Strike strike, Map<Player, Float> lanceDamage) {
        World world = Bukkit.getWorld(strike.worldId);
        if (world == null) {
            return;
        }
        int impactY = world.getHighestBlockAt((int) Math.floor(strike.x),
                (int) Math.floor(strike.z), HeightMap.WORLD_SURFACE).getY();
        switch (strike.kind) {
            case ShowConstants.STRIKE_GRASP -> graspImpact(strike, world, impactY);
            case ShowConstants.STRIKE_SIPHON -> siphonImpact(strike, world, impactY);
            case ShowConstants.STRIKE_BARRAGE -> barrageImpact(strike, world, impactY);
            case ShowConstants.STRIKE_LASER -> laserImpact(strike, world, lanceDamage);
            case ShowConstants.STRIKE_VORTEX -> vortexImpact(strike, world, impactY);
            case ShowConstants.STRIKE_RUPTURE -> ruptureImpact(strike, world, impactY);
            default -> boltImpact(strike, world, impactY);
        }
    }

    private void boltImpact(Strike strike, World world, int impactY) {
        world.spawnParticle(Particle.EXPLOSION_EMITTER, strike.x, impactY + 0.2, strike.z, 1, 0, 0, 0, 0);
        world.spawnParticle(Particle.ELECTRIC_SPARK, strike.x, impactY + 0.7, strike.z, 44,
                strike.radius * 0.7, 1.3, strike.radius * 0.7, 0.28);
        dust(world, 1.0F, 0.34F, 0.2F, 1.7F, strike.x, impactY + 0.4, strike.z, 60,
                strike.radius, 0.7, strike.radius, 0.22);
        world.playSound(new Location(world, strike.x, impactY, strike.z),
                Sound.ENTITY_LIGHTNING_BOLT_THUNDER, SoundCategory.WEATHER, 2.0F, 1.0F);
        world.playSound(new Location(world, strike.x, impactY, strike.z),
                Sound.ENTITY_LIGHTNING_BOLT_IMPACT, SoundCategory.WEATHER, 1.6F, 1.0F);
        for (Player player : victims(strike)) {
            hurt(player, strike.damage, BOLT);
            player.addPotionEffect(new PotionEffect(PotionEffectType.WEAKNESS, strike.debuffTicks, 0));
            player.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, strike.debuffTicks, 1));
            player.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS, strike.debuffTicks, 0));
            stormHitCount++;
        }
    }

    private void graspImpact(Strike strike, World world, int impactY) {
        dust(world, 0.72F, 0.30F, 1.0F, 2.0F, strike.x, impactY + 0.3, strike.z, 90,
                strike.radius, 0.5, strike.radius, 0.05);
        world.spawnParticle(Particle.ENCHANT, strike.x, impactY + 1.2, strike.z, 60,
                strike.radius, 1.6, strike.radius, 0.5);
        world.spawnParticle(Particle.SOUL, strike.x, impactY + 0.6, strike.z, 30,
                strike.radius * 0.6, 0.8, strike.radius * 0.6, 0.02);
        world.playSound(new Location(world, strike.x, impactY, strike.z),
                Sound.ENTITY_EVOKER_CAST_SPELL, SoundCategory.WEATHER, 2.0F, 0.7F);
        world.playSound(new Location(world, strike.x, impactY, strike.z),
                Sound.BLOCK_RESPAWN_ANCHOR_DEPLETE, SoundCategory.WEATHER, 1.6F, 1.4F);
        for (Player player : victims(strike)) {
            hurt(player, strike.damage, MAGIC);
            player.addPotionEffect(new PotionEffect(PotionEffectType.SLOWNESS, strike.debuffTicks, 6));
            player.addPotionEffect(new PotionEffect(PotionEffectType.NAUSEA, strike.debuffTicks, 0));
            player.addPotionEffect(new PotionEffect(PotionEffectType.WEAKNESS, strike.debuffTicks, 0));
            stormHitCount++;
        }
    }

    /** The drain cannot kill, so a player is left on a sliver, not the death screen. */
    private void siphonImpact(Strike strike, World world, int impactY) {
        dust(world, 1.0F, 0.08F, 0.06F, 1.8F, strike.x, impactY + 0.8, strike.z, 80,
                strike.radius * 0.5, 1.1, strike.radius * 0.5, 0.02);
        world.spawnParticle(Particle.SOUL, strike.x, impactY + 1.0, strike.z, 40,
                strike.radius * 0.5, 1.0, strike.radius * 0.5, 0.15);
        world.playSound(new Location(world, strike.x, impactY, strike.z),
                Sound.PARTICLE_SOUL_ESCAPE, SoundCategory.WEATHER, 2.0F, 0.6F);
        int drained = 0;
        for (Player player : victims(strike)) {
            float take = (float) Math.min(ShowConstants.SIPHON_DRAIN, player.getHealth() - 2.0);
            if (take > 0.0F && hurt(player, take, MAGIC)) {
                drained++;
            }
            player.addPotionEffect(new PotionEffect(PotionEffectType.NAUSEA, ShowConstants.STORM_DEBUFF_TICKS, 0));
            stormHitCount++;
        }
        Player boss = bossUuid == null ? null : Bukkit.getPlayer(bossUuid);
        if (boss != null && !boss.isDead() && drained > 0) {
            boss.setHealth(Math.min(maxHealth(boss),
                    boss.getHealth() + ShowConstants.SIPHON_BOSS_HEAL * drained));
            world.spawnParticle(Particle.HEART, boss.getLocation().getX(),
                    boss.getLocation().getY() + 1.8, boss.getLocation().getZ(),
                    Math.min(8, drained * 2), 0.6, 0.4, 0.6, 0.02);
        }
    }

    private void barrageImpact(Strike strike, World world, int impactY) {
        world.spawnParticle(Particle.EXPLOSION_EMITTER, strike.x, impactY + 0.2, strike.z, 1, 0, 0, 0, 0);
        dust(world, 1.0F, 0.55F, 0.15F, 1.6F, strike.x, impactY + 0.4, strike.z, 50,
                strike.radius, 0.6, strike.radius, 0.18);
        world.playSound(new Location(world, strike.x, impactY, strike.z),
                Sound.ENTITY_LIGHTNING_BOLT_IMPACT, SoundCategory.WEATHER, 1.2F, 1.35F);
        Player target = Bukkit.getPlayer(strike.player);
        if (target == null) {
            return;
        }
        for (int i = 0; i < ShowConstants.BARRAGE_SHARDS; i++) {
            double angle = Math.PI * 2.0 * i / ShowConstants.BARRAGE_SHARDS + strike.id * 0.7;
            Strike shard = new Strike(++nextStrikeId, target, ShowConstants.STRIKE_BOLT,
                    ShowConstants.BARRAGE_SHARD_WARN_TICKS, ShowConstants.BARRAGE_SHARD_RADIUS,
                    ShowConstants.BARRAGE_SHARD_DAMAGE, ShowConstants.STORM_DEBUFF_TICKS / 2, false, tickCount);
            shard.x = strike.x + Math.cos(angle) * 2.9;
            shard.z = strike.z + Math.sin(angle) * 2.9;
            shard.y = world.getHighestBlockAt((int) Math.floor(shard.x),
                    (int) Math.floor(shard.z), HeightMap.WORLD_SURFACE).getY();
            shard.startTick = tickCount + ShowConstants.BARRAGE_SHARD_DELAY * (i + 1);
            pendingStrikes.add(shard);
        }
    }

    private void vortexImpact(Strike strike, World world, int impactY) {
        dust(world, 1.0F, 0.08F, 0.58F, 1.8F, strike.x, impactY + 0.6, strike.z, 80,
                strike.radius * 0.7, 1.0, strike.radius * 0.7, 0.08);
        world.spawnParticle(Particle.SOUL, strike.x, impactY + 0.8, strike.z, 35,
                strike.radius * 0.5, 0.8, strike.radius * 0.5, 0.08);
        world.playSound(new Location(world, strike.x, impactY, strike.z),
                Sound.BLOCK_RESPAWN_ANCHOR_DEPLETE, SoundCategory.WEATHER, 1.6F, 0.6F);
        for (Player player : victims(strike)) {
            if (hurt(player, strike.damage, MAGIC)) {
                stormHitCount++;
            }
            double dx = strike.x - player.getLocation().getX();
            double dz = strike.z - player.getLocation().getZ();
            double distance = Math.sqrt(dx * dx + dz * dz);
            if (distance > 0.01) {
                double speed = Math.min(1.1, distance * 0.3);
                Vector v = player.getVelocity();
                player.setVelocity(new Vector(dx / distance * speed, Math.max(0.18, v.getY()),
                        dz / distance * speed));
            }
        }
    }

    private void ruptureImpact(Strike strike, World world, int impactY) {
        dust(world, 1.0F, 0.40F, 0.04F, 2.0F, strike.x, impactY + 1.2, strike.z, 80,
                strike.radius * 0.6, 2.0, strike.radius * 0.6, 0.14);
        world.spawnParticle(Particle.FLAME, strike.x, impactY + 0.5, strike.z, 40,
                strike.radius * 0.6, 0.5, strike.radius * 0.6, 0.12);
        world.playSound(new Location(world, strike.x, impactY, strike.z),
                Sound.ENTITY_GENERIC_EXPLODE, SoundCategory.WEATHER, 1.4F, 0.8F);
        for (Player player : victims(strike)) {
            if (hurt(player, strike.damage, MAGIC)) {
                stormHitCount++;
            }
            Vector v = player.getVelocity();
            player.setVelocity(new Vector(v.getX(), 0.8, v.getZ()));
        }
    }

    private void laserImpact(Strike strike, World world, Map<Player, Float> lanceDamage) {
        double y = strike.y;
        world.spawnParticle(Particle.EXPLOSION, strike.x, y, strike.z, 4, 0.35, 0.3, 0.35, 0.0);
        dust(world, 1.0F, 0.38F, 0.10F, 1.5F, strike.x, y, strike.z, 70, 0.4, 0.4, 0.4, 0.08);
        world.spawnParticle(Particle.ELECTRIC_SPARK, strike.x, y, strike.z, 50, 0.5, 0.5, 0.5, 0.45);
        // Only the centre lance sounds; overlapping cues would multiply the volley volume.
        if (strike.offsetX == 0.0 && strike.offsetZ == 0.0) {
            world.playSound(new Location(world, strike.x, y, strike.z),
                    Sound.BLOCK_BEACON_DEACTIVATE, SoundCategory.WEATHER, 2.0F, 0.6F);
            world.playSound(new Location(world, strike.x, y, strike.z),
                    Sound.ENTITY_LIGHTNING_BOLT_IMPACT, SoundCategory.WEATHER, 1.4F, 1.5F);
        }
        for (Player player : victims(strike)) {
            lanceDamage.merge(player, strike.damage, Float::sum);
        }
    }

    private List<Player> victims(Strike strike) {
        List<Player> hit = new ArrayList<>();
        for (Player player : Bukkit.getOnlinePlayers()) {
            if (!strikeable(player) || !player.getWorld().getUID().equals(strike.worldId)) {
                continue;
            }
            double dx = player.getLocation().getX() - strike.x;
            double dz = player.getLocation().getZ() - strike.z;
            double dy = player.getLocation().getY() - strike.y;
            if (dx * dx + dz * dz <= strike.radius * strike.radius && Math.abs(dy) <= 4.0) {
                hit.add(player);
            }
        }
        return hit;
    }

    /** Paper's damage() returns void, so a landed hit is read back from the health delta. */
    private static boolean hurt(Player player, double amount, DamageSource source) {
        double before = player.getHealth();
        player.damage(amount, source);
        return player.getHealth() < before;
    }

    private void stormParticles(Strike strike, boolean locked) {
        World world = Bukkit.getWorld(strike.worldId);
        if (world == null) {
            return;
        }
        float r;
        float g;
        float b;
        switch (strike.kind) {
            case ShowConstants.STRIKE_GRASP -> { r = 0.78F; g = locked ? 0.20F : 0.72F; b = 1.0F; }
            case ShowConstants.STRIKE_SIPHON -> { r = 1.0F; g = locked ? 0.05F : 0.72F; b = locked ? 0.04F : 0.66F; }
            case ShowConstants.STRIKE_BARRAGE -> { r = 1.0F; g = locked ? 0.42F : 0.82F; b = locked ? 0.05F : 0.55F; }
            case ShowConstants.STRIKE_VORTEX -> { r = 1.0F; g = locked ? 0.08F : 0.62F; b = locked ? 0.58F : 0.86F; }
            case ShowConstants.STRIKE_RUPTURE -> { r = 1.0F; g = locked ? 0.40F : 0.82F; b = locked ? 0.04F : 0.52F; }
            case ShowConstants.STRIKE_LASER -> { r = 1.0F; g = locked ? 0.32F : 0.86F; b = locked ? 0.05F : 0.52F; }
            default -> { r = locked ? 1.0F : 0.96F; g = locked ? 0.16F : 0.9F; b = locked ? 0.12F : 1.0F; }
        }
        Particle.DustOptions dust = new Particle.DustOptions(
                Color.fromRGB(Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)),
                locked ? 1.4F : 1.1F);
        int points = locked ? 14 : 7;
        for (int i = 0; i < points; i++) {
            double angle = Math.PI * 2.0 * i / points + strike.age * 0.11;
            world.spawnParticle(Particle.DUST,
                    strike.x + Math.cos(angle) * strike.radius, strike.y + 0.12,
                    strike.z + Math.sin(angle) * strike.radius, 1, 0, 0, 0, 0, dust);
        }
        // A slow rising spiral marks the column the attack will fall down.
        for (int i = 0; i < 3; i++) {
            double angle = strike.age * 0.35 + i * (Math.PI * 2.0 / 3.0);
            world.spawnParticle(Particle.ELECTRIC_SPARK,
                    strike.x + Math.cos(angle) * 0.7, strike.y + 0.4 + i * 0.7,
                    strike.z + Math.sin(angle) * 0.7, 1, 0, 0.02, 0, 0.0);
        }
        if (locked) {
            world.spawnParticle(Particle.ENCHANT, strike.x, strike.y + 1.0, strike.z,
                    4, 0.5, 0.6, 0.5, 0.4);
        }
    }

    private static void dust(World world, float r, float g, float b, float size,
                             double x, double y, double z, int count,
                             double dx, double dy, double dz, double extra) {
        world.spawnParticle(Particle.DUST, x, y, z, count, dx, dy, dz, extra,
                new Particle.DustOptions(Color.fromRGB(Math.round(r * 255), Math.round(g * 255),
                        Math.round(b * 255)), size));
    }

    private void cancelStrikes() {
        strikes.clear();
        pendingStrikes.clear();
    }

    // ------------------------------------------------------------------ victory

    private void grantFreeAdvancement() {
        if (freeGranted) {
            return;
        }
        freeGranted = true;
        Advancement advancement = Bukkit.getAdvancement(NamespacedKey.fromString("deusexmachina:server_free"));
        if (advancement == null) {
            plugin.getLogger().warning("Victory advancement missing - is the deusexmachina datapack enabled?");
            return;
        }
        for (Player player : Bukkit.getOnlinePlayers()) {
            AdvancementProgress progress = player.getAdvancementProgress(advancement);
            if (!progress.isDone()) {
                progress.awardCriteria("granted");
            }
            if (progress.isDone()) {
                freeGrantedCount++;
            }
        }
    }

    private void finishDefeat() {
        grantFreeAdvancement();
        message("The seal is broken. Server is finally free... at last.");
        beginClosing();
    }

    // ------------------------------------------------------------------ weather

    private World overworld() {
        World world = Bukkit.getWorld("world");
        return world != null ? world : Bukkit.getWorlds().get(0);
    }

    private void forceRain() {
        rainForced = true;
        World world = overworld();
        savedWeather = new boolean[] { world.hasStorm(), world.isThundering() };
        savedWeatherTimes = new int[] { world.getWeatherDuration(), world.getThunderDuration(),
                world.getClearWeatherDuration() };
        world.setClearWeatherDuration(0);
        world.setWeatherDuration(1000000);
        world.setStorm(true);
        world.setThundering(false);
    }

    private void restoreWeather() {
        if (!rainForced) {
            return;
        }
        rainForced = false;
        if (savedWeather == null) {
            return;
        }
        World world = overworld();
        world.setStorm(savedWeather[0]);
        world.setThundering(savedWeather[1]);
        world.setWeatherDuration(savedWeatherTimes[0]);
        world.setThunderDuration(savedWeatherTimes[1]);
        world.setClearWeatherDuration(savedWeatherTimes[2]);
        savedWeather = null;
    }

    // ------------------------------------------------------------------ freeze

    private void freeze(Player player) {
        if (frozen.containsKey(player.getUniqueId())) {
            return;
        }
        double[] originals = new double[4];
        AttributeInstance gravity = player.getAttribute(Attribute.GRAVITY);
        originals[3] = gravity != null ? gravity.getBaseValue() : 0.08;
        if (gravity != null) {
            gravity.setBaseValue(0.0);
        }
        originals[0] = setZero(player, Attribute.MOVEMENT_SPEED);
        originals[1] = setZero(player, Attribute.FLYING_SPEED);
        originals[2] = setZero(player, Attribute.JUMP_STRENGTH);
        frozen.put(player.getUniqueId(), originals);
        PersistentDataContainer pdc = player.getPersistentDataContainer();
        pdc.set(kFrozen, PersistentDataType.BYTE, (byte) 1);
        pdc.set(kSpeed, PersistentDataType.DOUBLE, originals[0]);
        pdc.set(kFly, PersistentDataType.DOUBLE, originals[1]);
        pdc.set(kJump, PersistentDataType.DOUBLE, originals[2]);
        pdc.set(kGravity, PersistentDataType.DOUBLE, originals[3]);
    }

    private static double setZero(Player player, Attribute attribute) {
        AttributeInstance instance = player.getAttribute(attribute);
        if (instance == null) {
            return 0.0;
        }
        double original = instance.getBaseValue();
        instance.setBaseValue(0.0);
        return original;
    }

    private void unfreeze(Player player) {
        double[] originals = frozen.remove(player.getUniqueId());
        PersistentDataContainer pdc = player.getPersistentDataContainer();
        if (originals == null && pdc.has(kFrozen)) {
            originals = new double[] {
                    pdc.getOrDefault(kSpeed, PersistentDataType.DOUBLE, 0.1),
                    pdc.getOrDefault(kFly, PersistentDataType.DOUBLE, 0.1),
                    pdc.getOrDefault(kJump, PersistentDataType.DOUBLE, 0.42),
                    pdc.getOrDefault(kGravity, PersistentDataType.DOUBLE, 0.08)
            };
        }
        if (originals != null) {
            restore(player, Attribute.MOVEMENT_SPEED, originals[0]);
            restore(player, Attribute.FLYING_SPEED, originals[1]);
            restore(player, Attribute.JUMP_STRENGTH, originals[2]);
            restore(player, Attribute.GRAVITY, originals[3]);
        }
        pdc.remove(kFrozen);
        pdc.remove(kSpeed);
        pdc.remove(kFly);
        pdc.remove(kJump);
        pdc.remove(kGravity);
    }

    private void recoverCrashFreeze(Player player) {
        if (player.getPersistentDataContainer().has(kFrozen)) {
            unfreeze(player);
        }
    }

    private static void restore(Player player, Attribute attribute, double value) {
        AttributeInstance instance = player.getAttribute(attribute);
        if (instance != null) {
            instance.setBaseValue(value);
        }
    }

    private void unfreezeAll() {
        for (Player player : Bukkit.getOnlinePlayers()) {
            unfreeze(player);
        }
        frozen.clear();
    }

    // ------------------------------------------------------------------ text

    private void message(String text) {
        Bukkit.broadcast(Component.text(text, NamedTextColor.DARK_RED));
    }

    private static String kindName(byte kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_GRASP -> "BINDING GRASP";
            case ShowConstants.STRIKE_SIPHON -> "BLOOD SIPHON";
            case ShowConstants.STRIKE_BARRAGE -> "EMBER BARRAGE";
            case ShowConstants.STRIKE_LASER -> "LANCE VOLLEY";
            case ShowConstants.STRIKE_VORTEX -> "VORTEX";
            case ShowConstants.STRIKE_RUPTURE -> "RUPTURE";
            default -> "LIGHTNING";
        };
    }

    private static String calloutColor(byte kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_GRASP -> "light_purple";
            case ShowConstants.STRIKE_SIPHON -> "dark_red";
            case ShowConstants.STRIKE_BARRAGE -> "yellow";
            case ShowConstants.STRIKE_LASER -> "gold";
            case ShowConstants.STRIKE_VORTEX -> "aqua";
            case ShowConstants.STRIKE_RUPTURE -> "white";
            default -> "red";
        };
    }
}