package net.deusexmachina.client;

import java.util.Arrays;

import net.deusexmachina.net.ShowBossPayload;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.util.Mth;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.api.distmarker.OnlyIn;

/**
 * Client copy of the RONOVA boss bar config, pushed by the server on start/stop, on login and
 * whenever the target's health changes. The raw {@link #hp()} is the server value; the render
 * reads the eased {@link #fill()} plus a fading damage trail and hit flash so hits feel weighty.
 *
 * <p>The health mechanic follows the dog mod's cosmic bar: ten notch segments that flare when
 * the fill edge sweeps past them, a recoil kick on any hit and a shake on a big one, a frame
 * flash when the possessed player takes hurt, a phase latch at half health and a flatline on
 * death. The RONOVA twist is molten: notches cool from white-hot to ember scars, healing
 * re-arms them, the phase is a crimson seal-break, and death draws an ECG flatline.
 */
@OnlyIn(Dist.CLIENT)
public final class ShowBoss {
    private static final int FLASH_TICKS = 7;
    private static final int GHOST_HOLD = 6;
    private static final int NOTCHES = 10;
    private static final long FAR_PAST = -10000L;

    private static boolean visible;
    private static String target = "";
    private static int hp;
    private static float displayed;
    private static float ghost;
    private static int ghostHold;
    private static int flash;

    private static final boolean[] notchCrossed = new boolean[NOTCHES];
    private static final long[] notchFlareMs = new long[NOTCHES];
    private static long recoilMs = FAR_PAST;
    private static long bigHitMs = FAR_PAST;
    private static long frameFlashMs = FAR_PAST;
    private static boolean phase2;
    private static long phase2Ms = -1L;
    private static long deathMs = -1L;
    private static int lastHurtTime;

    private ShowBoss() {
    }

    public static void handle(ShowBossPayload payload) {
        visible = payload.visible();
        target = payload.target();
        if (!visible) {
            hp = 0;
            displayed = 0.0F;
            ghost = 0.0F;
            ghostHold = 0;
            flash = 0;
            resetSegments();
            recoilMs = FAR_PAST;
            bigHitMs = FAR_PAST;
            frameFlashMs = FAR_PAST;
            phase2 = false;
            phase2Ms = -1L;
            deathMs = -1L;
            lastHurtTime = 0;
            return;
        }
        long now = System.currentTimeMillis();
        int next = payload.hp();
        if (next < hp) {
            ghost = Math.max(ghost, displayed);
            ghostHold = GHOST_HOLD;
            flash = FLASH_TICKS;
            int drop = hp - next;
            if (drop >= 1) {
                recoilMs = now;
            }
            if (drop >= 4) {
                bigHitMs = now;
            }
        }
        if (hp == 0 && next > 0) {
            // Respawning re-ignites the bar: scars cool away and the seal is whole again.
            resetSegments();
            phase2 = false;
            phase2Ms = -1L;
        }
        hp = next;
        boolean nextPhase2 = hp > 0 && payload.phase2();
        if (nextPhase2 && !phase2) {
            phase2Ms = now;
        } else if (!nextPhase2) {
            phase2Ms = -1L;
        }
        phase2 = nextPhase2;
        if (hp == 0) {
            if (deathMs < 0L) {
                deathMs = now;
            }
        } else {
            deathMs = -1L;
        }
    }

    private static void resetSegments() {
        Arrays.fill(notchCrossed, false);
        Arrays.fill(notchFlareMs, FAR_PAST);
    }

    /** Once per client tick: flare crossed notches, ease the fill, decay the trail and flash. */
    public static void tick() {
        if (!visible) {
            return;
        }
        long now = System.currentTimeMillis();
        // Checked before the ease so the ignition frame (fill still 0) flares every notch at once,
        // and a falling edge flares them one per tick as it sweeps down. Rising fill re-arms them.
        for (int i = 1; i < NOTCHES; i++) {
            float gate = i * (100.0F / NOTCHES);
            if (displayed < gate) {
                if (!notchCrossed[i]) {
                    notchCrossed[i] = true;
                    notchFlareMs[i] = now;
                }
            } else {
                notchCrossed[i] = false;
            }
        }
        displayed += (hp - displayed) * 0.3F;
        if (Math.abs(hp - displayed) < 0.05F) {
            displayed = hp;
        }
        if (ghostHold > 0) {
            ghostHold--;
        } else if (ghost > displayed) {
            ghost = Math.max(displayed, ghost - Math.max(0.6F, (ghost - displayed) * 0.12F));
        } else {
            ghost = displayed;
        }
        if (flash > 0) {
            flash--;
        }
        LocalPlayer player = Minecraft.getInstance().player;
        int hurt = player == null ? 0 : player.hurtTime;
        if (hurt > lastHurtTime && hurt >= 9) {
            frameFlashMs = now;
        }
        lastHurtTime = hurt;
    }

    public static boolean visible() {
        return visible;
    }

    public static String target() {
        return target;
    }

    public static int hp() {
        return hp;
    }

    public static float fill() {
        return displayed;
    }

    public static float ghostFill() {
        return Math.max(ghost, displayed);
    }

    public static float flashAlpha() {
        return flash / (float) FLASH_TICKS;
    }

    public static boolean low() {
        return visible && hp > 0 && hp <= 20;
    }

    public static int notchCount() {
        return NOTCHES;
    }

    public static boolean notchCrossed(int i) {
        return notchCrossed[i];
    }

    public static long notchFlareMs(int i) {
        return notchFlareMs[i];
    }

    public static int crossedCount() {
        int n = 0;
        for (boolean b : notchCrossed) {
            if (b) {
                n++;
            }
        }
        return n;
    }

    /** The dog's recoil curve: slide left over 80 ms, then spring back with a small overshoot. */
    public static float recoil() {
        long age = System.currentTimeMillis() - recoilMs;
        if (age < 0L || age >= 230L) {
            return 0.0F;
        }
        if (age < 80L) {
            return -2.0F * age / 80.0F;
        }
        float t = (age - 80L) / 150.0F;
        return -2.0F * (1.0F - t) + 0.7F * Mth.sin(t * (float) Math.PI);
    }

    public static boolean recoilHot() {
        long age = System.currentTimeMillis() - recoilMs;
        return age >= 0L && age < 120L;
    }

    public static long bigHitAge() {
        return System.currentTimeMillis() - bigHitMs;
    }

    /** 1 while the 100 ms white-hot frame flash from the player's own hurt is live, else 0. */
    public static float frameFlash() {
        long age = System.currentTimeMillis() - frameFlashMs;
        return age >= 0L && age < 100L ? 1.0F - age / 100.0F : 0.0F;
    }

    public static boolean phase2() {
        return phase2;
    }

    public static long phase2Age() {
        return phase2 ? System.currentTimeMillis() - phase2Ms : -1L;
    }

    /** Three staggered 60 ms white-hot flashes in the first 350 ms of the seal-break. */
    public static boolean phaseFlash() {
        long age = phase2Age();
        if (age < 0L || age >= 350L) {
            return false;
        }
        return age < 60L || (age >= 100L && age < 160L) || (age >= 220L && age < 280L);
    }

    public static boolean dead() {
        return visible && hp <= 0;
    }

    public static long deathAge() {
        return deathMs < 0L ? -1L : System.currentTimeMillis() - deathMs;
    }
}