package net.deusexmachina.client;

import java.util.ArrayList;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import net.deusexmachina.ShowConstants;
import net.deusexmachina.net.ShowStrikePayload;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.components.ContainerObjectSelectionList;
import net.minecraft.client.gui.components.events.GuiEventListener;
import net.minecraft.client.gui.screens.ConnectScreen;
import net.minecraft.client.gui.screens.DeathScreen;
import net.minecraft.client.gui.screens.DisconnectedScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.client.gui.screens.options.OptionsScreen;
import net.minecraft.client.gui.screens.options.SoundOptionsScreen;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.client.multiplayer.resolver.ServerAddress;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.client.resources.sounds.SoundInstance;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.level.levelgen.Heightmap;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.fml.common.EventBusSubscriber;
import net.neoforged.neoforge.client.event.ClientTickEvent;
import net.neoforged.neoforge.client.event.ScreenEvent;
import net.neoforged.neoforge.client.event.sound.PlaySoundEvent;
import net.neoforged.neoforge.common.NeoForge;

/**
 * DEVELOPMENT ONLY - this file is not part of the shipped jar.
 *
 * <p>Slider mode (default) opens the game's own Music &amp; Sound screen on the title screen,
 * screenshots it, checks the slider really sits one row under Ambient/Environment in the same
 * column, drives it with synthetic clicks, reads the config back off disk, posts a fake
 * {@code deusex:} sound through the event bus, reopens the screen to prove the slider does not
 * stack, and opens the plain Options screen to prove the old corner is empty.</p>
 *
 * <p>Show mode ({@code -PdeusexProbe=show}) joins the dev server at 127.0.0.1:25599 and drives
 * the whole 1.1.0 client-side show for real: it forces vanilla rain and screenshots it with the
 * show idle, runs {@code /function deusex:start} (which plays the build-up from the top),
 * screenshots the heart scene, the burst and lyrics, forces another downpour so the red tint can
 * be compared, pauses and resumes through the command bridge, kicks and rejoins mid-show to prove
 * the audio comes back, waits until 7:00 for the lyric band the user reported, restarts through
 * {@code /deusex start} to photograph the boss bar and its buff tiers, then stops the show and
 * waits for idle.</p>
 */
@EventBusSubscriber(modid = DeusExMachinaMod.MODID, value = Dist.CLIENT)
public final class DevProbe {
    private static final Logger LOG = LoggerFactory.getLogger("DEUSPROBE");
    private static final int ROW_HEIGHT = 25;
    private static final boolean SHOW = "show".equals(System.getProperty("deusex.probe", "slider"));
    private static final String ADDR = "127.0.0.1:25599";
    private static int tick = -1;
    private static SoundInstance playing;

    // show mode state
    private static int stage;
    private static int script;
    private static long pausedAt = -1L;
    private static boolean flashShot;
    private static boolean dropShot;
    private static boolean shotLyric;
    private static boolean shot420;
    private static boolean bossTestStarted;
    private static boolean bossTestDone;
    private static boolean bossScaleShot;
    private static long bossScaleAt;
    private static int bossOrigScale;
    private static int bossOrigW;
    private static int bossOrigH;
    private static int bossLiveStage;
    private static long bossLiveAt;
    private static int bossDeathAt;
    private static int bossHpBefore;
    private static boolean bossLiveDone;
    private static boolean bossRecoilSeen;
    private static boolean bossBigHitSeen;
    private static boolean bossFrameFlashSeen;
    private static boolean stopSent;
    private static int idleTicks;

    // storm proof: eat one bolt, dodge the next, then survive the rest of the show
    private static int stormStage;
    private static int stormStageAt;
    private static int stormHealthBefore;
    private static int stormHealthAt;
    private static int stormDodgeAt;
    private static int stormWarnShotAt;
    private static int stormLockShotAt;
    private static boolean stormWarnShot;
    private static boolean stormLockShot;
    private static boolean stormBoltShot;
    private static double stormMarkX;
    private static double stormMarkY;
    private static double stormMarkZ;
    private static boolean stormDodgeTeleported;

    // Graphics proof: a burst of corner frames stamped with the show tick so the harness can line
    // each one up with the baked drum envelope, then a client-injected SEAL LANCE so the new attack
    // dressing is photographed without spending a server wave.
    private static int gfxStage;
    private static int gfxAt;
    private static int cornerShot;
    private static double[] lanceMark;
    private static int lanceAt;
    private static boolean lanceImpactShot;

    // boss test restart, held until the heal from the storm damage has landed
    private static int bossStartAt;
    private static boolean bossStartSent;
    private static boolean bossSpareLogged;

    // Failsafe: if the show clock freezes or the audio pump keeps stalling, stop the probe early
    // and dump diagnostics instead of hanging until the safety timeout.
    private static final int FAILSAFE_FREEZE_TICKS = 600;
    private static final int FAILSAFE_MAX_RESTARTS = 4;
    private static long failsafeLastPos = -1L;
    private static int failsafeStall;
    private static boolean failsafeFired;

    private DevProbe() {}

    @SubscribeEvent
    public static void onTick(ClientTickEvent.Post event) {
        Minecraft mc = Minecraft.getInstance();
        if (SHOW) {
            try {
                showStep(mc);
            } catch (Throwable t) {
                LOG.error("DEUSPROBE show failed at stage {} script {}", stage, script, t);
                mc.stop();
            }
            return;
        }
        if (mc.level != null) {
            return;
        }
        // The window exists long before the title screen does, and nothing can be tested until the
        // screen is up: start the clock there rather than guessing at a boot time. The boot overlay
        // has to be gone too - while it is, it is what the game renders, so a screenshot taken now
        // shows the Mojang progress bar instead of the screen the widgets are really on.
        if (tick < 0) {
            if (mc.screen == null || mc.getOverlay() != null) {
                return;
            }
            tick = 0;
        }
        tick++;
        try {
            step(mc);
        } catch (Throwable t) {
            LOG.error("DEUSPROBE failed at tick {}", tick, t);
            mc.stop();
        }
    }

    private static void step(Minecraft mc) {
        switch (tick) {
            case 1 -> {
                LOG.info("DEUSPROBE opening the Music & Sound screen");
                mc.setScreen(new SoundOptionsScreen(mc.screen, mc.options));
            }
            case 16 -> {
                report(mc.screen, "45 default");
                Screenshot.grab(mc.gameDirectory, "deusex-sound-default.png", mc.getMainRenderTarget(),
                        c -> LOG.info("DEUSPROBE screenshot default: {}", c.getString()));
            }
            case 20 -> {
                AbstractWidget slider = find(mc.screen);
                if (slider == null) {
                    LOG.info("DEUSPROBE no slider on the screen");
                    return;
                }
                // onClick maps mouseX to value (mouseX - x - 4) / (width - 8), so this click asks
                // for 20%.
                LOG.info("DEUSPROBE click to 20 consumed={} -> MusicVolume.get()={} config={}",
                        drag(slider, 0.2), MusicVolume.get(), readConfig());
            }
            case 24 -> Screenshot.grab(mc.gameDirectory, "deusex-sound-after-click.png", mc.getMainRenderTarget(),
                    c -> LOG.info("DEUSPROBE screenshot click: {}", c.getString()));
            case 28 -> {
                // Not a MusicVolume.Scaled on purpose: the listener's own guard refuses to wrap
                // something it already wrapped, so the fake has to reach the bus as a plain
                // instance for the scaling to be the listener's doing rather than the probe's.
                SoundInstance fake = new SimpleSoundInstance(SoundEvents.ITEM_PICKUP, SoundSource.RECORDS,
                        1.0F, 1.0F, SoundInstance.createUnseededRandom(), BlockPos.ZERO) {
                    @Override
                    public ResourceLocation getLocation() {
                        return ResourceLocation.fromNamespaceAndPath("deusex", "probe");
                    }
                };
                // An AbstractSoundInstance only knows its volume after resolve() has picked a Sound
                // out of the registry, which is exactly what SoundEngine.play does before it asks.
                fake.resolve(mc.getSoundManager());
                float before = fake.getVolume();
                PlaySoundEvent ev = new PlaySoundEvent(null, fake);
                NeoForge.EVENT_BUS.post(ev);
                SoundInstance out = ev.getSound();
                LOG.info("DEUSPROBE sound: posted {} with volume {} -> engine received {} with volume {} "
                                + "(expected {} at {} percent)",
                        fake.getClass().getName(), before, out.getClass().getName(), out.getVolume(),
                        before * MusicVolume.scale(), MusicVolume.get());

                SoundInstance vanilla = SimpleSoundInstance.forUI(SoundEvents.AMBIENT_CAVE, 1.0F);
                PlaySoundEvent ev2 = new PlaySoundEvent(null, vanilla);
                NeoForge.EVENT_BUS.post(ev2);
                LOG.info("DEUSPROBE gate: a minecraft: sound came through as {} (must be unchanged: {})",
                        ev2.getSound().getClass().getName(), vanilla.getClass().getName());

                mc.getSoundManager().play(out);
                playing = out;
                LOG.info("DEUSPROBE engine accepted the wrapped instance, isActive={}",
                        mc.getSoundManager().isActive(out));
            }
            case 32 -> {
                // The claim in the tooltip: moving the slider changes what is already playing. This
                // click goes through set(), which re-reads the volume of every live instance, so a
                // throw here is the song dying mid-drag for the player.
                AbstractWidget slider = find(mc.screen);
                boolean moved = slider != null && drag(slider, 0.8);
                LOG.info("DEUSPROBE drag to 80 consumed={} -> MusicVolume.get()={} wrapped volume now {} "
                                + "(expected {}) still playing={}",
                        moved, MusicVolume.get(), playing == null ? -1 : playing.getVolume(),
                        MusicVolume.scale(), mc.getSoundManager().isActive(playing));
            }
            case 34 -> {
                // The voice row was rebuilt around the same widget: its option binding has to
                // survive, so a click on it must still reach the game's own voice volume.
                AbstractWidget voice = voice(mc.screen);
                boolean moved = voice != null && drag(voice, 0.5);
                LOG.info("DEUSPROBE voice click consumed={} -> options voice volume={} (expected 0.5)",
                        moved, mc.options.getSoundSourceVolume(SoundSource.VOICE));
            }
            case 36 -> {
                // Esc and back into Music & Sound is a brand new screen object and the listener runs
                // again on it. It has to add exactly one slider, in the same cell, reading 80%.
                mc.setScreen(new SoundOptionsScreen(mc.screen, mc.options));
            }
            case 40 -> {
                report(mc.screen, "reopened at 80");
                AbstractWidget slider = find(mc.screen);
                LOG.info("DEUSPROBE reopened at 80 - sliders on screen={} (must be 1) message=[{}]",
                        count(mc.screen), slider == null ? "<none>" : slider.getMessage().getString());
                Screenshot.grab(mc.gameDirectory, "deusex-sound-reopened.png", mc.getMainRenderTarget(),
                        c -> LOG.info("DEUSPROBE screenshot reopened: {}", c.getString()));
            }
            case 44 -> {
                // The slider used to live in the bottom-right corner of the plain Options screen.
                // That corner has to be empty now - the control moved, it was not copied.
                mc.setScreen(new OptionsScreen(mc.screen, mc.options));
            }
            case 48 -> {
                LOG.info("DEUSPROBE plain Options - sliders on screen={} (must be 0)", count(mc.screen));
                Screenshot.grab(mc.gameDirectory, "deusex-options-clean.png", mc.getMainRenderTarget(),
                        c -> LOG.info("DEUSPROBE screenshot options: {}", c.getString()));
            }
            case 52 -> {
                LOG.info("DEUSPROBE reloading config: {}", readConfig());
                mc.stop();
            }
            default -> {
                // nothing else to do
            }
        }
    }

    /** Drives the widget the way a click on the track does, and says whether it took the click. */
    private static boolean drag(AbstractWidget slider, double fraction) {
        double mx = slider.getX() + 4 + fraction * (slider.getWidth() - 8);
        return slider.mouseClicked(mx, slider.getY() + slider.getHeight() / 2.0, 0);
    }

    private static String readConfig() {
        try {
            java.util.Properties p = new java.util.Properties();
            try (java.io.InputStream in = java.nio.file.Files.newInputStream(
                    net.neoforged.fml.loading.FMLPaths.CONFIGDIR.get()
                            .resolve(DeusExMachinaMod.MODID + "-client.properties"))) {
                p.load(in);
            }
            return p.getProperty("song-volume");
        } catch (Exception e) {
            return "<none: " + e.getClass().getSimpleName() + ">";
        }
    }

    private static int count(Screen screen) {
        int n = 0;
        for (AbstractWidget w : widgets(screen)) {
            if (w.getClass().getName().contains("MusicVolume$Slider")) {
                n++;
            }
        }
        return n;
    }

    private static AbstractWidget find(Screen screen) {
        for (AbstractWidget w : widgets(screen)) {
            if (w.getClass().getName().contains("MusicVolume$Slider")) {
                return w;
            }
        }
        return null;
    }

    private static AbstractWidget ambient(Screen screen) {
        String label = Component.translatable("soundCategory.ambient").getString();
        for (AbstractWidget w : widgets(screen)) {
            if (w.getMessage().getString().startsWith(label)) {
                return w;
            }
        }
        return null;
    }

    private static AbstractWidget voice(Screen screen) {
        String label = Component.translatable("soundCategory.voice").getString();
        for (AbstractWidget w : widgets(screen)) {
            if (w.getMessage().getString().startsWith(label)) {
                return w;
            }
        }
        return null;
    }

    private static void report(Screen screen, String tag) {
        List<AbstractWidget> all = widgets(screen);
        AbstractWidget slider = find(screen);
        if (slider == null) {
            LOG.info("DEUSPROBE {} - no slider among {} widgets", tag, all.size());
            return;
        }
        Minecraft mc = Minecraft.getInstance();
        LOG.info("DEUSPROBE {} - slider x={} y={} w={} h={} message=[{}] widgets total={}",
                tag, slider.getX(), slider.getY(), slider.getWidth(), slider.getHeight(),
                slider.getMessage().getString(), all.size());
        AbstractWidget ambient = ambient(screen);
        if (ambient == null) {
            LOG.info("DEUSPROBE {} - no Ambient/Environment widget found among the rows", tag);
            return;
        }
        // The list paints rows 25 pixels apart and Entry.render puts the right child of every row
        // at the same x, so "below Ambient/Environment" is exactly same x, y one row down.
        LOG.info("DEUSPROBE {} - ambient x={} y={} message=[{}] | same column={} one row below={} (dy={}) "
                        + "inside screen={}",
                tag, ambient.getX(), ambient.getY(), ambient.getMessage().getString(),
                slider.getX() == ambient.getX(),
                slider.getY() - ambient.getY() == ROW_HEIGHT, slider.getY() - ambient.getY(),
                slider.getX() >= 0 && slider.getY() >= 0
                        && slider.getX() + slider.getWidth() <= mc.getWindow().getGuiScaledWidth()
                        && slider.getY() + slider.getHeight() <= mc.getWindow().getGuiScaledHeight());
        AbstractWidget voice = voice(screen);
        if (voice != null) {
            // Entry.render walks a row's children left then right, 160 pixels apart: sharing the
            // voice row means same y as Voice/Speech and exactly one column stride left of it.
            LOG.info("DEUSPROBE {} - voice x={} y={} message=[{}] | same row as slider={} "
                            + "one column left of ambient={} (dx={})",
                    tag, voice.getX(), voice.getY(), voice.getMessage().getString(),
                    voice.getY() == slider.getY(),
                    ambient.getX() - voice.getX() == 160, ambient.getX() - voice.getX());
        }
    }

    /** Every widget on the screen, including the ones nested in the option list's rows. */
    private static List<AbstractWidget> widgets(Screen screen) {
        List<AbstractWidget> out = new ArrayList<>();
        for (GuiEventListener listener : screen.children()) {
            collect(listener, out);
        }
        return out;
    }

    private static void collect(GuiEventListener listener, List<AbstractWidget> out) {
        if (listener instanceof AbstractWidget widget) {
            out.add(widget);
        }
        if (listener instanceof ContainerObjectSelectionList<?> list) {
            for (ContainerObjectSelectionList.Entry<?> entry : list.children()) {
                for (GuiEventListener child : entry.children()) {
                    collect(child, out);
                }
            }
        }
    }

    // ---------------------------------------------------------------- show mode

    private static void showStep(Minecraft mc) {
        switch (stage) {
            case 0 -> {
                if (mc.screen == null || mc.getOverlay() != null) {
                    return;
                }
                LOG.info("DEUSPROBE show: title up, connecting to {}", ADDR);
                connect(mc);
                stage = 1;
            }
            case 1 -> {
                if (inWorld(mc)) {
                    enterWorld(mc);
                }
            }
            case 2 -> {
                failsafe(mc);
                if (!failsafeFired) {
                    script(mc);
                }
            }
            case 3 -> {
                if (mc.screen instanceof DisconnectedScreen) {
                    LOG.info("DEUSPROBE show: kicked, reconnecting to {}", ADDR);
                    connect(mc);
                    stage = 4;
                }
            }
            case 4 -> {
                if (inWorld(mc)) {
                    onRejoined(mc);
                }
            }
            case 5 -> {
                failsafe(mc);
                if (!failsafeFired) {
                    afterRejoin(mc);
                }
            }
            default -> { }
        }
    }

    private static void connect(Minecraft mc) {
        ServerData data = new ServerData("deus probe", ADDR, ServerData.Type.OTHER);
        ConnectScreen.startConnecting(new TitleScreen(), mc, ServerAddress.parseString(ADDR), data, false, null);
    }

    private static boolean inWorld(Minecraft mc) {
        return mc.level != null && mc.player != null && mc.getConnection() != null
                && mc.getOverlay() == null && mc.screen == null;
    }

    private static void enterWorld(Minecraft mc) {
        LOG.info("DEUSPROBE show: joined as {}", mc.player.getGameProfile().getName());
        cmd(mc, "gamemode survival");
        cmd(mc, "time set noon");
        cmd(mc, "gamerule doDaylightCycle false");
        // Teleporting to a hardcoded y buried the player in this world; use the surface under
        // the spawn columns instead so the probe never starts on the death screen.
        int x = mc.player.getBlockX();
        int z = mc.player.getBlockZ();
        int y = mc.level.getHeight(Heightmap.Types.MOTION_BLOCKING, x, z) + 2;
        cmd(mc, "tp " + mc.player.getGameProfile().getName() + " " + x + " " + y + " " + z);
        mc.player.setXRot(-45.0F);
        mc.player.setYRot(30.0F);
        script = 0;
        stage = 2;
    }

    private static void script(Minecraft mc) {
        script++;
        shotFlashIfAny(mc);
        shotDrop(mc);
        stormStep(mc);
        gfxStep(mc);
        switch (script) {
            case 10 -> {
                cmd(mc, "weather rain");
                state("rain-command");
            }
            case 110 -> {
                state("vanilla-rain");
                LOG.info("DEUSPROBE show: vanilla rain must be untinted - active={} rainRed={}",
                        ShowTimeline.active(), ShowTimeline.rainRed());
                shot(mc, "deusex-vanilla-rain.png");
            }
            case 130 -> cmd(mc, "weather clear");
            case 160 -> cmd(mc, "function deusex:start");
            // ACT_START carries sample 0: the show opens on the quiet build-up, so the clock must
            // crawl up from the top instead of jumping into the heart scene.
            case 168 -> state("started");
            // The heart scene begins at tick 42; sample it once the ring is actually on screen.
            case 220 -> state("intro");
            case 560 -> {
                state("show-rain");
                shot(mc, "deusex-show-rain.png");
            }
            case 600 -> {
                cmd(mc, "function deusex:pause");
                state("paused");
            }
            // Sample after the ACT_PAUSE payload has arrived, or this measures the audio that
            // played while the command was in flight, not the clock the pause froze.
            case 610 -> pausedAt = ShowClient.position();
            case 660 -> {
                long p2 = ShowClient.position();
                LOG.info("DEUSPROBE show: pause held - pos {} -> {} equal={} state={} (expect 2)",
                        pausedAt, p2, p2 == pausedAt, ShowClient.state());
            }
            case 680 -> {
                cmd(mc, "function deusex:resume");
                state("resumed");
            }
            case 720 -> LOG.info("DEUSPROBE show: resumed advanced - pos {} -> {} (expect >) state={} "
                    + "(expect 1)", pausedAt, ShowClient.position(), ShowClient.state());
            // The strike proof owns the ticks right after the resume (wave one lands, wave two is
            // dodged), so the rejoin kick waits until it has stepped to creative.
            case 1000 -> {
                LOG.info("DEUSPROBE show: kicking self to test rejoin");
                cmd(mc, "kick " + mc.player.getGameProfile().getName());
                stage = 3;
            }
            default -> { }
        }
    }

    private static void onRejoined(Minecraft mc) {
        LOG.info("DEUSPROBE show: rejoined - state={} (expect 1) pos={} ticks={} phase={} sound flows "
                        + "from here", ShowClient.state(), ShowClient.position(),
                ticks(), ShowTimeline.phase());
        state("rejoined");
        shot(mc, "deusex-rejoined.png");
        script = 0;
        stage = 5;
    }

    private static void afterRejoin(Minecraft mc) {
        script++;
        shotFlashIfAny(mc);
        stormStep(mc);
        gfxStep(mc);
        long t = ticks();
        if (script % 200 == 0) {
            state("running " + t);
        }
        // The first lyric window opens at tick 1069; this frame lands inside one.
        if (!shotLyric && t >= 1240L && ShowTimeline.lyricCell() >= 0) {
            state("lyric");
            shot(mc, "deusex-lyric.png");
            shotLyric = true;
        }
        if (!shot420 && t >= 8400L) {
            int want = lyricWindow(t);
            int cell = ShowTimeline.lyricCell();
            if (want >= 0) {
                LOG.info("DEUSPROBE show: 7:00 lyric - ticks={} window={} cell={} match={}",
                        t, want, cell, cell / 6 == want);
                shot(mc, "deusex-lyric-420.png");
                shot420 = true;
            } else if (t >= 8600L) {
                LOG.info("DEUSPROBE show: 7:00 lyric - no window from 8400 to {} (window={})", t, want);
                shot420 = true;
            }
        }
        if (!stopSent && t >= 8520L) {
            cmd(mc, "function deusex:stop");
            stopSent = true;
            state("stopping");
            shot(mc, "deusex-closing.png");
        }
        if (stopSent) {
            if (ShowClient.state() == 0) {
                idleTicks++;
            } else {
                idleTicks = 0;
            }
            // The scripted run is over; restart through the boss-bar command and capture the bar.
            if (idleTicks == 20 && !bossTestStarted) {
                bossTestStarted = true;
                String name = mc.player.getGameProfile().getName();
                // The storm left the player hurt, and the bar reads live health as its fraction:
                // start it on a full player or the opening frame would already look half dead.
                cmd(mc, "gamemode survival");
                cmd(mc, "effect give " + name + " minecraft:instant_health 1 4");
                cmd(mc, "advancement revoke " + name + " only deusexmachina:server_free");
                bossStartAt = script + 20;
                LOG.info("DEUSPROBE show: boss test prep - health={} reverting to survival, "
                        + "healing, revoking the free-server advancement", mc.player.getHealth());
            }
            if (bossTestStarted && !bossStartSent && script >= bossStartAt) {
                String name = mc.player.getGameProfile().getName();
                if (mc.player.getHealth() >= 19.0F || script > bossStartAt + 20) {
                    bossStartSent = true;
                    cmd(mc, "deusex start " + name + " 75");
                    LOG.info("DEUSPROBE show: boss test - restarted via /deusex start at health {}",
                            mc.player.getHealth());
                }
            }
            if (bossStartSent && !bossSpareLogged && ShowClient.state() == net.deusexmachina.ShowConstants.STATE_PLAYING
                    && ShowStrike.wave() >= 1) {
                // First wave of the boss show: the bar's bearer must never be among the marked.
                bossSpareLogged = true;
                state("boss-spared");
                LOG.info("DEUSPROBE show: boss spared - wave={} targets={} marks={} boss={} spared={} "
                                + "(expect targets 0, marks 0, spared true)",
                        ShowStrike.wave(), ShowStrike.waveTargets(), ShowStrike.strikes().size(),
                        ShowStrike.boss(), ShowStrike.spared());
                shot(mc, "deusex-bossbar-spared.png");
            }
            if (bossTestStarted && !bossTestDone && ShowClient.state() == net.deusexmachina.ShowConstants.STATE_PLAYING
                    && ticks() >= 300L && ShowTimeline.phase() == ShowTimeline.PH_SONG) {
                bossTestDone = true;
                state("bossbar");
                shot(mc, "deusex-bossbar.png");
                LOG.info("DEUSPROBE show: bossbar - visible={} target={} hp={}",
                        ShowBoss.visible(), ShowBoss.target(), ShowBoss.hp());
                bossOrigScale = mc.options.guiScale().get();
                bossOrigW = mc.getWindow().getScreenWidth();
                bossOrigH = mc.getWindow().getScreenHeight();
                // Scale 4 only fits a >=1280x960 framebuffer; the resize callback re-runs
                // resizeDisplay and applies the new option once the window actually grows.
                org.lwjgl.glfw.GLFW.glfwSetWindowSize(mc.getWindow().getWindow(), 1280, 960);
                mc.options.guiScale().set(4);
                bossScaleAt = ticks();
            }
            if (bossTestDone && !bossScaleShot && ticks() >= bossScaleAt + 40L) {
                bossScaleShot = true;
                shot(mc, "deusex-bossbar-scale4.png");
                LOG.info("DEUSPROBE show: bossbar scale4 - guiScale={}", mc.getWindow().getGuiScale());
                mc.options.guiScale().set(bossOrigScale);
                org.lwjgl.glfw.GLFW.glfwSetWindowSize(mc.getWindow().getWindow(), bossOrigW, bossOrigH);
                // Let the window settle back to its original size, then prove the bar tracks live health.
                bossLiveStage = 1;
                bossLiveAt = ticks() + 30L;
            }
            if (bossLiveStage > 0 && !bossLiveDone) {
                bossLiveStep(mc);
            }
            if (idleTicks == 20 && bossLiveDone) {
                LOG.info("DEUSPROBE show: idle reached {} ticks after stop, rainRed={} (expect 0, false)",
                        ShowClient.position(), ShowTimeline.rainRed());
                LOG.info("DEUSPROBE show: done");
                mc.stop();
            }
        }
        if (script > 20000) {
            LOG.info("DEUSPROBE show: safety timeout at ticks {}", t);
            mc.stop();
        }
    }

    /**
     * During the boss-live proof the flatline shot must show the bar, not the "You died!" overlay.
     * setScreen(null) cannot close it - Minecraft re-opens DeathScreen whenever a dead player has
     * no screen - so cancel the opening itself, both from the combat-kill packet and the tick retry.
     */
    @SubscribeEvent
    public static void onScreenOpening(ScreenEvent.Opening event) {
        if (bossLiveStage > 0 && !bossLiveDone && event.getNewScreen() instanceof DeathScreen) {
            event.setCanceled(true);
        }
    }

    /**
     * Live HP proof: damage shrinks the bar, a heal regrows it, a big hit crosses notch segments and
     * breaks the phase seal, death empties it into a flatline and respawn re-ignites it. Each step
     * waits for the server health broadcast to land and the fill ease to settle before sampling, so
     * the logged hp is what a viewer actually sees, not the command in flight. The transient hit
     * reactions (recoil, big-hit shake, frame flash) are polled every tick while waiting.
     */
    private static void bossLiveStep(Minecraft mc) {
        if (ShowBoss.recoil() != 0.0F) {
            bossRecoilSeen = true;
        }
        if (ShowBoss.bigHitAge() < 400L) {
            bossBigHitSeen = true;
        }
        if (ShowBoss.frameFlash() > 0.0F) {
            bossFrameFlashSeen = true;
        }
        // The CLOSING->IDLE transition resets the show position, so ticks() drops to 0 while the
        // defeat watch still waits for it. Only the timed damage steps wait on ticks().
        if (bossLiveStage < 8 && ticks() < bossLiveAt) {
            return;
        }
        String name = mc.player.getGameProfile().getName();
        int hp = ShowBoss.hp();
        switch (bossLiveStage) {
            case 1 -> {
                bossHpBefore = hp;
                LOG.info("DEUSPROBE show: bossbar live start - hp={} buffs=[{}] (expect 75)",
                        hp, buffs(mc));
                cmd(mc, "damage " + name + " 6");
                bossLiveStage = 2;
                bossLiveAt = ticks() + 30L;
            }
            case 2 -> {
                shot(mc, "deusex-bossbar-hurt.png");
                LOG.info("DEUSPROBE show: bossbar hurt - hp={} before={} dropped={} buffs=[{}]",
                        hp, bossHpBefore, hp < bossHpBefore, buffs(mc));
                cmd(mc, "effect give " + name + " minecraft:instant_health 1 4");
                bossLiveStage = 3;
                bossLiveAt = ticks() + 30L;
            }
            case 3 -> {
                LOG.info("DEUSPROBE show: bossbar heal - hp={} before={} restored={}",
                        hp, bossHpBefore, hp >= bossHpBefore);
                // 10 of the player's 20 health lands the bar near 38%: past the half-health seal
                // but alive, so the phase and notch shots show the bar, not the death screen.
                cmd(mc, "damage " + name + " 10");
                bossLiveStage = 4;
                bossLiveAt = ticks() + 6L;
            }
            case 4 -> {
                shot(mc, "deusex-bossbar-notch.png");
                LOG.info("DEUSPROBE show: bossbar notch - hp={} crossed={} recoil={} bigHit={} "
                                + "frameFlash={} buffs=[{}]",
                        hp, ShowBoss.crossedCount(), bossRecoilSeen, bossBigHitSeen, bossFrameFlashSeen,
                        buffs(mc));
                bossLiveStage = 5;
                bossLiveAt = ticks() + 24L;
            }
            case 5 -> {
                shot(mc, "deusex-bossbar-phase2.png");
                LOG.info("DEUSPROBE show: bossbar phase2 - hp={} phase2={} buffs=[{}] (expect true)",
                        hp, ShowBoss.phase2(), buffs(mc));
                cmd(mc, "damage " + name + " 100");
                bossLiveStage = 6;
                bossLiveAt = ticks() + 30L;
            }
            case 6 -> {
                LOG.info("DEUSPROBE show: bossbar death - hp={} emptied={}", hp, hp == 0);
                shot(mc, "deusex-bossbar-flat.png");
                bossDeathAt = script;
                bossLiveStage = 7;
                // The defeat path holds the flatline for BOSS_DEATH_LINGER, then grants the
                // advancement to everyone online and closes the show on its own.
            }
            case 7 -> {
                int state = ShowClient.state();
                if (state == net.deusexmachina.ShowConstants.STATE_CLOSING) {
                    LOG.info("DEUSPROBE show: boss defeat - state={} barVisible={} (expect 3, false)",
                            state, ShowBoss.visible());
                    shot(mc, "deusex-free.png");
                    bossLiveStage = 8;
                } else if (state == net.deusexmachina.ShowConstants.STATE_PLAYING
                        && script > bossDeathAt + 120) {
                    LOG.info("DEUSPROBE show: boss defeat - show still playing {} ticks after the "
                            + "kill (expect closing)", script - bossDeathAt);
                    bossLiveStage = 8;
                }
            }
            case 8 -> {
                if (ShowClient.state() == net.deusexmachina.ShowConstants.STATE_IDLE) {
                    LOG.info("DEUSPROBE show: boss death stopped the event - state=0 barVisible={} "
                            + "- advancement toast captured in deusex-free.png", ShowBoss.visible());
                    bossLiveDone = true;
                    bossLiveStage = 9;
                }
            }
            default -> { }
        }
    }

    /**
     * Watch the playing show for the freeze the user reported. If the show clock stops advancing,
     * or the audio watchdog has to restart the song over and over, stop the probe right away and
     * dump everything needed to diagnose it rather than idling until the safety timeout.
     */
    private static void failsafe(Minecraft mc) {
        if (failsafeFired) {
            return;
        }
        if (ShowClient.state() != net.deusexmachina.ShowConstants.STATE_PLAYING) {
            failsafeStall = 0;
            failsafeLastPos = ShowClient.position();
            return;
        }
        long pos = ShowClient.position();
        if (pos > failsafeLastPos) {
            failsafeLastPos = pos;
            failsafeStall = 0;
        } else if (++failsafeStall >= FAILSAFE_FREEZE_TICKS) {
            fireFailsafe(mc, "show clock frozen at sample " + pos + " for " + failsafeStall + " ticks");
            return;
        }
        if (ShowClient.watchdogRestarts() >= FAILSAFE_MAX_RESTARTS) {
            fireFailsafe(mc, "audio pump stalled repeatedly (" + ShowClient.watchdogRestarts()
                    + " watchdog restarts)");
        }
    }

    private static void fireFailsafe(Minecraft mc, String reason) {
        failsafeFired = true;
        LOG.error("DEUSPROBE FAILSAFE triggered: {}", reason);
        LOG.error("DEUSPROBE FAILSAFE state={} pos={} ticks={} phase={} loop={}",
                ShowClient.state(), ShowClient.position(), ticks(), ShowTimeline.phase(), ShowClient.loop());
        LOG.error("DEUSPROBE FAILSAFE audio: {}", ShowClient.debugAudio());
        LOG.error("DEUSPROBE FAILSAFE volumes master={} record={} music={} songSlider={} scale={}",
                mc.options.getSoundSourceVolume(SoundSource.MASTER),
                mc.options.getSoundSourceVolume(SoundSource.RECORDS),
                mc.options.getSoundSourceVolume(SoundSource.MUSIC),
                MusicVolume.get(), MusicVolume.scale());
        LOG.error("DEUSPROBE FAILSAFE sound engine: {}", mc.getSoundManager().getDebugString());
        for (var entry : Thread.getAllStackTraces().entrySet()) {
            Thread thread = entry.getKey();
            String name = thread.getName().toLowerCase(java.util.Locale.ROOT);
            if (name.contains("sound") || name.contains("audio")) {
                StringBuilder trace = new StringBuilder();
                for (StackTraceElement element : entry.getValue()) {
                    trace.append("\n    at ").append(element);
                }
                LOG.error("DEUSPROBE FAILSAFE thread {} state={}{}", thread.getName(), thread.getState(), trace);
            }
        }
        shot(mc, "deusex-failsafe.png");
        cmd(mc, "function deusex:stop");
        LOG.error("DEUSPROBE FAILSAFE shutting down the probe for analysis");
        mc.stop();
    }

    private static void shotFlashIfAny(Minecraft mc) {
        float flash = ShowTimeline.skyFlash();
        if (!flashShot && flash > 0.6F) {
            flashShot = true;
            LOG.info("DEUSPROBE show: sky flash {} at ticks {} wash={}", flash, ticks(),
                    ShowTimeline.wash(0.5F));
            shot(mc, "deusex-skyflash.png");
        }
    }

    /**
     * Wait for a rendered burst frame instead of a fixed tick: the display paints one frame behind
     * the synced clock, so the drop tick itself still shows the last heart frame.
     */
    private static void shotDrop(Minecraft mc) {
        if (dropShot || ShowTimeline.phase() != ShowTimeline.PH_BURST) {
            return;
        }
        if (ShowTimeline.burstFrame(ticks()) >= 2) {
            shot(mc, "deusex-drop.png");
            dropShot = true;
            state("drop");
        }
    }

    /**
     * The storm proof, driven off the client's own marks: stand in the first one to prove a failed
     * dodge costs health and lands the three debuffs, then step eight blocks out of the second at
     * the lock to prove a clean dodge leaves the health alone. Once both are logged the probe goes
     * creative so the rest of the seven-minute show cannot kill it.
     */
    private static void stormStep(Minecraft mc) {
        if (mc.player == null || stormStage >= 10) {
            return;
        }
        switch (stormStage) {
            case 0 -> {
                if (ShowStrike.strikes().isEmpty()) {
                    return;
                }
                // XRot positive looks down. The probe has been framing the sky; aim at the mark so
                // the ground sigil and its reticle are actually in the frame, then let the camera
                // settle for two ticks before grabbing the warning.
                mc.player.setXRot(60.0F);
                stormHealthBefore = Math.round(mc.player.getHealth());
                state("storm-warn");
                LOG.info("DEUSPROBE show: storm warning - wave={} targets={} marks={} health={} "
                                + "(expect wave 1, targets 1, marks 1)",
                        ShowStrike.wave(), ShowStrike.waveTargets(), ShowStrike.strikes().size(),
                        mc.player.getHealth());
                stormWarnShotAt = script + 2;
                enterStorm(1);
            }
            case 1 -> {
                if (!stormWarnShot && script >= stormWarnShotAt) {
                    stormWarnShot = true;
                    shot(mc, "deusex-strike.png");
                }
                for (ShowStrike.Strike strike : ShowStrike.strikes()) {
                    if (!strike.locked()) {
                        continue;
                    }
                    LOG.info("DEUSPROBE show: storm locked - id={} ticksLeft={} urgency={}",
                            strike.id, strike.ticksLeft, strike.urgency());
                    stormLockShotAt = script + 2;
                    enterStorm(2);
                    return;
                }
                if (script > stormStageAt + 80) {
                    LOG.info("DEUSPROBE show: storm lock never observed - marks={} (expect a locked mark)",
                            ShowStrike.strikes().size());
                    stormHealthAt = script + 40;
                    enterStorm(3);
                }
            }
            case 2 -> {
                if (!stormLockShot && script >= stormLockShotAt) {
                    stormLockShot = true;
                    shot(mc, "deusex-strike-lock.png");
                }
                boolean struck = ShowStrike.strikes().isEmpty()
                        && ShowStrike.hitAge() <= ShowStrike.hitWindow();
                if (!struck && script <= stormStageAt + 40) {
                    return;
                }
                // The damage and effect packets travel in the same flush as the impact; read twice
                // later so the health and debuff log is what the player really ended up with.
                stormHealthAt = script + 2;
                enterStorm(3);
            }
            case 3 -> {
                if (script < stormHealthAt) {
                    return;
                }
                int health = Math.round(mc.player.getHealth());
                LOG.info("DEUSPROBE show: storm hit - health {} -> {} dropped={} hitAge={} effects=[{}] "
                                + "(expect 8 damage, weakness/slowness/blindness about 80 ticks)",
                        stormHealthBefore, health, health < stormHealthBefore,
                        ShowStrike.hitAge(), effects(mc));
                shot(mc, "deusex-strike-impact.png");
                enterStorm(4);
            }
            case 4 -> {
                if (ShowStrike.strikes().isEmpty()) {
                    return;
                }
                stormHealthBefore = Math.round(mc.player.getHealth());
                LOG.info("DEUSPROBE show: storm dodge start - wave={} health={}",
                        ShowStrike.wave(), mc.player.getHealth());
                enterStorm(5);
            }
            case 5 -> {
                if (stormDodgeTeleported) {
                    return;
                }
                for (ShowStrike.Strike strike : ShowStrike.strikes()) {
                    if (!strike.locked()) {
                        continue;
                    }
                    stormDodgeTeleported = true;
                    stormMarkX = strike.rx();
                    stormMarkY = strike.ry();
                    stormMarkZ = strike.rz();
                    // The lock has already pinned the point; eight blocks is well outside the
                    // three-block radius, so this is a real escape from a real bolt.
                    cmd(mc, "tp " + mc.player.getGameProfile().getName() + " ~8 ~ ~");
                    LOG.info("DEUSPROBE show: storm dodge - stepped 8 blocks out of mark {} with {} "
                            + "ticks to the bolt", strike.id, strike.ticksLeft);
                    enterStorm(6);
                    return;
                }
                if (script > stormStageAt + 80) {
                    LOG.info("DEUSPROBE show: storm dodge lock never observed - marks={}",
                            ShowStrike.strikes().size());
                    enterStorm(6);
                }
            }
            case 6 -> {
                boolean missed = ShowStrike.strikes().isEmpty()
                        && ShowStrike.dodgeAge() <= ShowStrike.dodgeWindow();
                if (missed && !stormBoltShot) {
                    // Stand outside the mark and face it, so the custom bolt is framed from the
                    // side while it is at full height instead of from inside the trunk.
                    stormBoltShot = true;
                    double dx = stormMarkX - mc.player.getX();
                    double dz = stormMarkZ - mc.player.getZ();
                    mc.player.setYRot((float) Math.toDegrees(Math.atan2(-dx, dz)));
                    mc.player.setXRot(-6.0F);
                    shot(mc, "deusex-strike-bolt.png");
                }
                if (!missed && script <= stormStageAt + 120) {
                    return;
                }
                stormDodgeAt = script + 2;
                enterStorm(7);
            }
            case 7 -> {
                if (script < stormDodgeAt) {
                    return;
                }
                int health = Math.round(mc.player.getHealth());
                // Natural regeneration can only raise the health here, so "not lower" is the dodge:
                // a failed dodge is 12 damage and three fresh debuffs.
                boolean untouched = health >= stormHealthBefore;
                boolean dodged = ShowStrike.dodgeAge() <= ShowStrike.dodgeWindow();
                String debuffs = stormDebuffs(mc);
                LOG.info("DEUSPROBE show: storm dodge - health {} -> {} untouched={} dodged={} "
                                + "dodgeAge={} debuffs=[{}] (expect true, true, none)",
                        stormHealthBefore, health, untouched, dodged, ShowStrike.dodgeAge(), debuffs);
                // Waves three and four land while the probe is still online; creative keeps them
                // from undoing the proof before the boss test needs a full player.
                cmd(mc, "gamemode creative");
                mc.player.setXRot(-45.0F);
                enterStorm(8);
            }
            case 8 -> enterStorm(9);
            case 9 -> enterStorm(10);
            default -> { }
        }
    }

    /** The three storm debuffs currently on the player, so a clean dodge reads empty. */
    private static String stormDebuffs(Minecraft mc) {
        if (mc.player == null) {
            return "";
        }
        List<String> parts = new ArrayList<>();
        for (var effect : mc.player.getActiveEffects()) {
            String id = effect.getEffect().unwrapKey().map(k -> k.location().getPath()).orElse("?");
            if (id.equals("weakness") || id.equals("slowness") || id.equals("blindness")) {
                parts.add(id + ":" + effect.getDuration());
            }
        }
        parts.sort(null);
        return String.join(",", parts);
    }

    private static void enterStorm(int next) {
        stormStage = next;
        stormStageAt = script;
    }

    /**
     * The graphics proof. Once the storm checks are done, take a short burst of frames in a quiet
     * song section - each stamped with the show tick, so the harness can compare its corners with
     * the baked drum envelope - and then feed the client its own SEAL LANCE mark at a point four
     * blocks ahead: one for the warning, one for the locked fuse and one for the impact. The mark
     * is client-local (id 9001 never collides with a server strike), so no wave is spent and the
     * server never damages the probe for it.
     */
    private static void gfxStep(Minecraft mc) {
        if (mc.player == null || stormStage < 10 || (stage != 2 && stage != 5)) {
            return;
        }
        switch (gfxStage) {
            case 0 -> {
                // A live mark's own edge vignette paints the same corners, so wait for the gap
                // between waves before sampling the drum flash.
                if (ShowClient.state() != ShowConstants.STATE_PLAYING
                        || ShowTimeline.phase() != ShowTimeline.PH_SONG
                        || !ShowStrike.strikes().isEmpty() || ShowStrike.endangered()) {
                    return;
                }
                LOG.info("DEUSPROBE show: graphics proof start tick={}", ticks());
                gfxStage = 1;
                gfxAt = script;
                cornerShot = 0;
            }
            case 1 -> {
                if (script < gfxAt) {
                    gfxAt = script;
                }
                if (script - gfxAt < cornerShot * 2) {
                    return;
                }
                shot(mc, "deusex-corner-" + cornerShot + ".png");
                LOG.info("DEUSPROBE show: corner - shot={} ticks={}", cornerShot, ticks());
                cornerShot++;
                if (cornerShot >= 8) {
                    gfxStage = 2;
                    gfxAt = script;
                }
            }
            case 2 -> {
                if (!ShowStrike.strikes().isEmpty() && script - gfxAt < 200) {
                    return;
                }
                double yaw = Math.toRadians(mc.player.getYRot());
                lanceMark = new double[] {
                        mc.player.getX() - Math.sin(yaw) * 4.0,
                        mc.player.getEyeY() - 0.15,
                        mc.player.getZ() + Math.cos(yaw) * 4.0};
                mc.player.setXRot(-14.0F);
                lanceAt = script;
                LOG.info("DEUSPROBE show: lance warn - mark=[{},{},{}] warn={} (client-injected)",
                        lanceMark[0], lanceMark[1], lanceMark[2], ShowConstants.LASER_WARN_TICKS);
                gfxStage = 3;
            }
            case 3 -> {
                int age = script - lanceAt;
                if (age >= 26) {
                    gfxStage = 4;
                    lanceAt = script;
                    return;
                }
                lance(ShowConstants.LASER_WARN_TICKS - age, ShowStrikePayload.TRACKING);
                if (age == 10) {
                    shot(mc, "deusex-laser-warn.png");
                    LOG.info("DEUSPROBE show: lance warn frame - laser={} marks={}",
                            lanceDecoded(), ShowStrike.strikes().size());
                }
            }
            case 4 -> {
                int age = script - lanceAt;
                if (age >= 16) {
                    lance(0, ShowStrikePayload.IMPACT);
                    gfxStage = 5;
                    lanceAt = script;
                    return;
                }
                lance(26 - age, ShowStrikePayload.LOCKED);
                if (age == 8) {
                    shot(mc, "deusex-laser-lock.png");
                    LOG.info("DEUSPROBE show: lance locked frame - laser={} marks={}",
                            lanceDecoded(), ShowStrike.strikes().size());
                }
            }
            case 5 -> {
                if (!lanceImpactShot && script - lanceAt >= 2) {
                    lanceImpactShot = true;
                    shot(mc, "deusex-laser-impact.png");
                    LOG.info("DEUSPROBE show: lance impact frame - impacts={}",
                            ShowStrike.impacts().size());
                    gfxStage = 6;
                }
            }
            default -> { }
        }
    }

    private static void lance(int ticksLeft, byte state) {
        byte phase = (byte) ((ShowConstants.STRIKE_LASER << 2) | state);
        ShowStrike.handle(new ShowStrikePayload(9001, lanceMark[0], lanceMark[1], lanceMark[2],
                Math.max(0, ticksLeft), phase));
    }

    private static boolean lanceDecoded() {
        for (ShowStrike.Strike strike : ShowStrike.strikes()) {
            if (strike.id == 9001) {
                return strike.laser();
            }
        }
        return false;
    }

    /** Non-ambient effects as id:amplifier:ticks, sorted, so a missing debuff shows in the log. */
    private static String effects(Minecraft mc) {
        if (mc.player == null) {
            return "";
        }
        List<String> parts = new ArrayList<>();
        for (var effect : mc.player.getActiveEffects()) {
            if (effect.isAmbient()) {
                continue;
            }
            String id = effect.getEffect().unwrapKey().map(k -> k.location().getPath()).orElse("?");
            parts.add(id + ":" + effect.getAmplifier() + ":" + effect.getDuration());
        }
        parts.sort(null);
        return String.join(",", parts);
    }

    private static long ticks() {
        return ShowClient.position() / net.deusexmachina.ShowConstants.SAMPLES_PER_TICK;
    }

    /** Ambient effects the bar lends its target, sorted as registry-id:amplifier pairs. */
    private static String buffs(Minecraft mc) {
        if (mc.player == null) {
            return "";
        }
        List<String> parts = new ArrayList<>();
        for (var effect : mc.player.getActiveEffects()) {
            if (!effect.isAmbient()) {
                continue;
            }
            String id = effect.getEffect().unwrapKey().map(k -> k.location().getPath()).orElse("?");
            parts.add(id + ":" + effect.getAmplifier());
        }
        parts.sort(null);
        return String.join(",", parts);
    }

    private static int lyricWindow(long ticks) {
        for (int i = 0; i < ShowHudData.LYRIC_START.length; i++) {
            if (ticks >= ShowHudData.LYRIC_START[i] && ticks < ShowHudData.LYRIC_END[i]) {
                return i;
            }
        }
        return -1;
    }

    private static void state(String tag) {
        LOG.info("DEUSPROBE show {}: state={} pos={} ticks={} phase={} wash={} rainRed={} skyFlash={} "
                        + "lyricCell={} loop={}",
                tag, ShowClient.state(), ShowClient.position(), ticks(), ShowTimeline.phase(),
                ShowTimeline.wash(0.5F), ShowTimeline.rainRed(), ShowTimeline.skyFlash(),
                ShowTimeline.lyricCell(), ShowClient.loop());
    }

    private static void cmd(Minecraft mc, String command) {
        if (mc.getConnection() != null) {
            mc.getConnection().sendCommand(command);
        }
    }

    private static void shot(Minecraft mc, String name) {
        Screenshot.grab(mc.gameDirectory, name, mc.getMainRenderTarget(),
                c -> LOG.info("DEUSPROBE show screenshot {}: {}", name, c.getString()));
    }
}
