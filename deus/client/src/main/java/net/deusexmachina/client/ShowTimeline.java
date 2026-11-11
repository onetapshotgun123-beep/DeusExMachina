package net.deusexmachina.client;

import java.util.Random;
import net.deusexmachina.ShowConstants;
import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.RandomSource;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.api.distmarker.OnlyIn;

/**
 * The show timeline, ported from the datapack's tick functions. Everything is
 * derived from the heard audio sample (ShowClient.position), so pause, lag and
 * rejoin land on the same frame the ear is at. Tick() runs on the client tick;
 * the render side reads the cached state and lerps the wash between ticks.
 */
@OnlyIn(Dist.CLIENT)
public final class ShowTimeline {
    public static final int PH_IDLE = 0;
    public static final int PH_BLACKOUT = 1;
    public static final int PH_HEART = 2;
    public static final int PH_BURST = 3;
    public static final int PH_SONG = 4;
    public static final int PH_CLOSING = 5;

    private static final ResourceLocation HEARTBEAT = ResourceLocation.fromNamespaceAndPath("deusexmachina", "heartbeat");
    private static final ResourceLocation BOOM = ResourceLocation.fromNamespaceAndPath("deusexmachina", "boom");
    private static final ResourceLocation BOOM_RISE = ResourceLocation.fromNamespaceAndPath("deusexmachina", "boom_rise");

    private static int phase = PH_IDLE;
    private static long lastTicks = -1L;
    private static boolean wasPlaying;

    private static float wash;
    private static float prevWash;
    private static int washDrain;

    private static int flashCountdown = 200;
    private static int flashAge = -1;
    private static long lcg;

    private static final Random RANDOM = new Random();
    private static int glitchLeft;
    private static int hudPreset;
    private static int discFrame;
    private static int timeSec;
    private static int dispMin;
    private static int dispS10;
    private static int dispS1;
    private static int lyricCell = -1;
    private static long lastHudDraw = -1L;

    private static int closingTick;
    private static int closingFrame;
    private static int closingPreset;
    private static int closingMin;
    private static int closingS10;
    private static int closingS1;
    private static SimpleSoundInstance lastHeartbeat;

    private ShowTimeline() {
    }

    public static void tick() {
        int state = ShowClient.state();
        if (state == ShowConstants.STATE_PAUSED) {
            return;
        }
        if (state == ShowConstants.STATE_CLOSING) {
            if (phase != PH_CLOSING) {
                phase = PH_CLOSING;
                closingTick = 0;
                closingFrame = 0;
                wash = 17.0F;
                prevWash = wash;
                washDrain = 0;
                stopHeartbeat();
            }
            tickClosing();
            return;
        }
        if (state != ShowConstants.STATE_PLAYING) {
            if (phase != PH_IDLE) {
                phase = PH_IDLE;
                wasPlaying = false;
                lastTicks = -1L;
                wash = 0.0F;
                prevWash = 0.0F;
                flashAge = -1;
                lyricCell = -1;
                stopHeartbeat();
            }
            return;
        }

        long ticks = ShowClient.position() / ShowConstants.SAMPLES_PER_TICK;
        if (!wasPlaying) {
            wasPlaying = true;
            lastTicks = ticks - 1L;
            glitchLeft = 0;
            hudPreset = 0;
            lastHudDraw = -1L;
            flashCountdown = 200;
            flashAge = -1;
            washDrain = 0;
            if (ShowClient.loop()) {
                phase = PH_SONG;
                wash = 14.0F;
            } else {
                wash = 0.0F;
            }
            prevWash = wash;
        }
        if (ShowClient.loop() && phase == PH_SONG && ticks < lastTicks - 100L) {
            lastTicks = ticks - 1L;
            lastHudDraw = -1L;
        }

        prevWash = wash;
        int oldPhase = phase;
        if (ticks < 42L) {
            phase = PH_BLACKOUT;
            wash = 0.0F;
        } else if (ticks < ShowConstants.DROP_TICKS) {
            phase = PH_HEART;
            fireIntroSounds(ticks);
            int hb = heartAge(ticks);
            wash = hb < ShowHudData.HB_WASH.length ? ShowHudData.HB_WASH[hb] : 0.0F;
        } else if (ticks < ShowConstants.DROP_TICKS + 50L) {
            phase = PH_BURST;
            if (oldPhase == PH_HEART) {
                fireBoom();
            }
            long k = ticks - ShowConstants.DROP_TICKS;
            wash = Math.min(14L, k + 1L);
        } else {
            phase = PH_SONG;
            if (oldPhase == PH_BURST) {
                flashCountdown = 200;
            }
            tickFlashAndWash();
        }

        if (phase == PH_BURST || phase == PH_SONG) {
            tickHud(ticks);
        } else {
            lyricCell = -1;
        }
        lastTicks = ticks;
    }

    private static int heartAge(long ticks) {
        int hb = 99;
        for (int i = ShowHudData.BEAT_TICKS.length - 1; i >= 0; i--) {
            if (ticks >= ShowHudData.BEAT_TICKS[i]) {
                hb = (int) (ticks - ShowHudData.BEAT_TICKS[i]);
                break;
            }
        }
        return Math.min(hb, 99);
    }

    private static void fireIntroSounds(long ticks) {
        for (int beat : ShowHudData.BEAT_TICKS) {
            if (ticks >= beat && lastTicks < beat && ticks - beat <= 2L) {
                lastHeartbeat = play(HEARTBEAT);
            }
        }
        long rise = ShowConstants.DROP_TICKS - 7L;
        if (ticks >= rise && lastTicks < rise && ticks - rise <= 2L) {
            play(BOOM_RISE);
        }
    }

    private static void fireBoom() {
        stopHeartbeat();
        play(BOOM);
    }

    private static void stopHeartbeat() {
        if (lastHeartbeat != null) {
            Minecraft.getInstance().getSoundManager().stop(lastHeartbeat);
            lastHeartbeat = null;
        }
    }

    private static SimpleSoundInstance play(ResourceLocation location) {
        SimpleSoundInstance sound = new SimpleSoundInstance(location, SoundSource.RECORDS, 1.0F, 1.0F,
            RandomSource.create(), false, 0, net.minecraft.client.resources.sounds.SoundInstance.Attenuation.NONE,
            0.0, 0.0, 0.0, true);
        Minecraft.getInstance().getSoundManager().play(sound);
        return sound;
    }

    private static void tickFlashAndWash() {
        if (flashAge >= 0) {
            flashAge++;
            if (flashAge >= 22) {
                flashAge = -1;
            }
        } else {
            flashCountdown--;
            if (flashCountdown <= 0) {
                flashAge = 0;
                wash = 17.0F;
                washDrain = 0;
                lcg = lcg * 1103515245L + 12345L;
                flashCountdown = (int) Math.floorMod(lcg, 261L) + 160;
            }
        }
        if (wash < 14.0F) {
            wash = Math.min(14.0F, wash + 1.0F);
        } else if (wash > 14.0F) {
            washDrain++;
            if (washDrain >= 4) {
                washDrain = 0;
                wash = Math.max(14.0F, wash - 1.0F);
            }
        }
    }

    private static void tickHud(long ticks) {
        long draw = ticks / 2L;
        if (draw != lastHudDraw) {
            lastHudDraw = draw;
            discFrame = (int) Math.floorMod(draw, 24L);
            if (glitchLeft > 0) {
                glitchLeft--;
                hudPreset = 1 + RANDOM.nextInt(10);
            } else if (RANDOM.nextInt(100) < 5) {
                glitchLeft = 1 + RANDOM.nextInt(5);
                hudPreset = 1 + RANDOM.nextInt(10);
            } else {
                hudPreset = 0;
            }
            timeSec = (int) (ticks / 20L);
            int min = timeSec / 60;
            int sec = timeSec % 60;
            dispMin = min;
            dispS10 = sec / 10;
            dispS1 = sec % 10;
            if (ShowHudData.P_SCR[hudPreset] == 1) {
                dispMin = RANDOM.nextInt(10);
                dispS10 = RANDOM.nextInt(6);
                dispS1 = RANDOM.nextInt(10);
            }
        }
        lyricCell = lyricAt(ticks);
    }

    private static int lyricAt(long ticks) {
        for (int i = 0; i < ShowHudData.LYRIC_START.length; i++) {
            if (ticks >= ShowHudData.LYRIC_START[i] && ticks < ShowHudData.LYRIC_END[i]) {
                long le = ticks - ShowHudData.LYRIC_START[i];
                long rem = ShowHudData.LYRIC_END[i] - ticks;
                int a = (int) Math.min(5L, le);
                int b = (int) Math.min(5L, rem * 6L / 8L);
                return i * 6 + Math.min(a, b);
            }
        }
        return -1;
    }

    private static void tickClosing() {
        prevWash = wash;
        closingTick++;
        washDrain++;
        if (washDrain >= 4 && wash > 0.0F) {
            washDrain = 0;
            wash = Math.max(0.0F, wash - 1.0F);
        }
        if (closingTick < 40) {
            closingFrame = (closingFrame + 2) % 24;
            closingPreset = 1 + RANDOM.nextInt(10);
            closingMin = RANDOM.nextInt(10);
            closingS10 = RANDOM.nextInt(6);
            closingS1 = RANDOM.nextInt(10);
        }
        if (closingTick >= 56 && wash <= 0.0F) {
            phase = PH_IDLE;
        }
    }

    public static int phase() {
        return phase;
    }

    public static boolean active() {
        return phase != PH_IDLE;
    }

    /** Wash level 0..17, interpolated between ticks for a smooth fade. */
    public static float wash(float partialTick) {
        return prevWash + (wash - prevWash) * partialTick;
    }

    public static float blackoutAlpha(long ticks) {
        return Math.min(1.0F, ticks / 40.0F);
    }

    public static int heartFrame(long ticks) {
        return Math.min(heartAge(ticks), 12);
    }

    public static int burstFrame(long ticks) {
        long k = ticks - ShowConstants.DROP_TICKS;
        if (k <= 0L) {
            return 0;
        }
        if (k == 1L) {
            return 1;
        }
        return (int) Math.min(15L, 2L + (k - 2L) / 3L);
    }

    /** Sky flash intensity 0..1 for the sky-color mixin; -1 when no flash. */
    public static float skyFlash() {
        return flashAge >= 0 && flashAge < 22 ? ShowHudData.FLASH_GLOW[flashAge] / 255.0F : 0.0F;
    }

    public static int hudPreset() {
        return hudPreset;
    }

    public static int discFrame() {
        return discFrame;
    }

    public static int timeSec() {
        return timeSec;
    }

    public static int dispMin() {
        return dispMin;
    }

    public static int dispS10() {
        return dispS10;
    }

    public static int dispS1() {
        return dispS1;
    }

    public static int lyricCell() {
        return lyricCell;
    }

    public static int closingTick() {
        return closingTick;
    }

    public static int closingFrame() {
        return closingFrame;
    }

    public static int closingPreset() {
        return closingPreset;
    }

    public static int closingMin() {
        return closingMin;
    }

    public static int closingS10() {
        return closingS10;
    }

    public static int closingS1() {
        return closingS1;
    }

    public static boolean rainRed() {
        int state = ShowClient.state();
        return (state == ShowConstants.STATE_PLAYING || state == ShowConstants.STATE_PAUSED)
            && ShowClient.position() >= ShowConstants.ticksToSamples(ShowConstants.RAIN_TICKS);
    }
}