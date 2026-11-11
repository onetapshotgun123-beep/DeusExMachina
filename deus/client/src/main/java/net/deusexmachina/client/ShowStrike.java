package net.deusexmachina.client;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import net.deusexmachina.ShowConstants;
import net.deusexmachina.net.ShowStormPayload;
import net.deusexmachina.net.ShowStrikePayload;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.util.Mth;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.api.distmarker.OnlyIn;

/**
 * Client copy of the storm: one mark per player the server has targeted, plus the local player's
 * own near-miss and hit feedback. Positions are pushed every tick while the mark tracks a player
 * and freeze for the last second before the bolt, so the ring on screen is the ring the server
 * will strike. Marks that stop being updated for a while are dropped, which keeps a lost show from
 * leaving a sigil burning in the world.
 */
@OnlyIn(Dist.CLIENT)
public final class ShowStrike {
    /** How long the impact bloom lingers after the bolt lands. */
    private static final long IMPACT_MS = 700L;
    private static final long WAVE_MS = 2600L;
    private static final long HIT_MS = 420L;
    private static final long DODGE_MS = 900L;
    private static final long STALE_MS = 3000L;
    /** Marks interpolate over one server update at 20 Hz, so 20 Hz tracking looks continuous. */
    private static final double LERP_MS = 50.0;

    /** One tracked mark, as the server last described it. */
    public static final class Strike {
        public final int id;
        public byte phase;
        public byte kind;
        public int warnTicks;
        public double prevX;
        public double prevY;
        public double prevZ;
        public double x;
        public double y;
        public double z;
        public float radius;
        public int ticksLeft;
        long updatedMs;
        long seenMs;

        Strike(int id) {
            this.id = id;
            this.warnTicks = ShowConstants.STORM_WARN_TICKS;
        }

        public double rx() {
            return Mth.lerp(progress(), prevX, x);
        }

        public double ry() {
            return Mth.lerp(progress(), prevY, y);
        }

        public double rz() {
            return Mth.lerp(progress(), prevZ, z);
        }

        private double progress() {
            return Mth.clamp((System.currentTimeMillis() - updatedMs) / LERP_MS, 0.0, 1.0);
        }

        public boolean locked() {
            return phase == ShowStrikePayload.LOCKED;
        }

        /** 0 at the first warning tick, 1 at the attack lands. */
        public float urgency() {
            int total = Math.max(1, warnTicks);
            return Mth.clamp(1.0F - ticksLeft / (float) total, 0.0F, 1.0F);
        }

        public boolean bolt() {
            return kind == ShowConstants.STRIKE_BOLT;
        }

        public boolean grasp() {
            return kind == ShowConstants.STRIKE_GRASP;
        }

        public boolean siphon() {
            return kind == ShowConstants.STRIKE_SIPHON;
        }

        public boolean barrage() {
            return kind == ShowConstants.STRIKE_BARRAGE;
        }

        public boolean laser() {
            return kind == ShowConstants.STRIKE_LASER;
        }

        public boolean vortex() {
            return kind == ShowConstants.STRIKE_VORTEX;
        }

        public boolean rupture() {
            return kind == ShowConstants.STRIKE_RUPTURE;
        }
    }

    /** A landed attack, kept for the ground bloom and the local screen reaction. */
    public static final class Impact {
        public final double x;
        public final double y;
        public final double z;
        public final float radius;
        public final byte kind;
        public final long startMs;

        Impact(double x, double y, double z, float radius, byte kind, long startMs) {
            this.x = x;
            this.y = y;
            this.z = z;
            this.radius = radius;
            this.kind = kind;
            this.startMs = startMs;
        }

        public float life() {
            return Mth.clamp(1.0F - (System.currentTimeMillis() - startMs) / (float) IMPACT_MS, 0.0F, 1.0F);
        }

        public boolean bolt() {
            return kind == ShowConstants.STRIKE_BOLT;
        }

        public boolean laser() {
            return kind == ShowConstants.STRIKE_LASER;
        }

        public boolean vortex() {
            return kind == ShowConstants.STRIKE_VORTEX;
        }

        public boolean rupture() {
            return kind == ShowConstants.STRIKE_RUPTURE;
        }
    }

    private static final List<Strike> strikes = new ArrayList<>();
    private static final List<Impact> impacts = new ArrayList<>();

    private static int wave;
    private static int waveTargets;
    private static byte wavePrimaryKind = -1;
    private static byte waveSecondaryKind = -1;
    private static String boss = "";
    private static long waveMs = -10000L;
    private static long hitMs = -10000L;
    private static long dodgeMs = -10000L;

    private ShowStrike() {
    }

    public static void handle(ShowStrikePayload payload) {
        long now = System.currentTimeMillis();
        int packed = payload.phase() & 0xFF;
        int state = packed & 0x3;
        // Six kind bits, two state bits: the payload packs kind << 2 | state.
        int kind = (packed >> 2) & 0x3F;
        if (state == ShowStrikePayload.CANCELLED) {
            remove(payload.id());
            return;
        }
        if (state == ShowStrikePayload.IMPACT) {
            Strike strike = remove(payload.id());
            float radius = strike != null ? strike.radius : radiusFor(kind);
            impacts.add(new Impact(payload.x(), payload.y(), payload.z(), radius, (byte) kind, now));
            react(payload.x(), payload.y(), payload.z(), radius, now);
            return;
        }
        Strike strike = find(payload.id());
        if (strike == null) {
            strike = new Strike(payload.id());
            strike.prevX = payload.x();
            strike.prevY = payload.y();
            strike.prevZ = payload.z();
            // A new mark always arrives with its full fuse, so this is the kind's warn length.
            strike.warnTicks = Math.max(1, payload.ticksLeft());
            strikes.add(strike);
        } else {
            strike.prevX = strike.rx();
            strike.prevY = strike.ry();
            strike.prevZ = strike.rz();
        }
        strike.x = payload.x();
        strike.y = payload.y();
        strike.z = payload.z();
        strike.kind = (byte) kind;
        strike.radius = radiusFor(kind);
        strike.phase = (byte) state;
        strike.ticksLeft = payload.ticksLeft();
        strike.updatedMs = now;
        strike.seenMs = now;
    }

    private static float radiusFor(int kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_GRASP -> ShowConstants.GRASP_RADIUS;
            case ShowConstants.STRIKE_SIPHON -> ShowConstants.SIPHON_RADIUS;
            case ShowConstants.STRIKE_BARRAGE -> ShowConstants.STORM_RADIUS;
            case ShowConstants.STRIKE_LASER -> ShowConstants.LASER_RADIUS;
            case ShowConstants.STRIKE_VORTEX -> ShowConstants.VORTEX_RADIUS;
            case ShowConstants.STRIKE_RUPTURE -> ShowConstants.RUPTURE_RADIUS;
            default -> ShowConstants.STORM_RADIUS;
        };
    }

    public static void handleStorm(ShowStormPayload payload) {
        wave = payload.wave();
        waveTargets = payload.targets();
        wavePrimaryKind = payload.primaryKind();
        waveSecondaryKind = payload.secondaryKind();
        boss = payload.boss() == null ? "" : payload.boss();
        waveMs = System.currentTimeMillis();
    }

    public static void tick() {
        if (ShowClient.state() == ShowConstants.STATE_IDLE) {
            reset();
            return;
        }
        long now = System.currentTimeMillis();
        impacts.removeIf(impact -> now - impact.startMs > IMPACT_MS);
        // A mark that stops talking to us belongs to a show that is no longer running.
        for (Iterator<Strike> it = strikes.iterator(); it.hasNext(); ) {
            if (now - it.next().seenMs > STALE_MS) {
                it.remove();
            }
        }
    }

    public static void reset() {
        strikes.clear();
        impacts.clear();
        wave = 0;
        waveTargets = 0;
        wavePrimaryKind = -1;
        waveSecondaryKind = -1;
        boss = "";
        waveMs = -10000L;
        hitMs = -10000L;
        dodgeMs = -10000L;
    }

    public static boolean active() {
        return !strikes.isEmpty() || !impacts.isEmpty() || waveAge() < WAVE_MS || hitAge() < HIT_MS;
    }

    public static List<Strike> strikes() {
        return strikes;
    }

    public static List<Impact> impacts() {
        return impacts;
    }

    public static int wave() {
        return wave;
    }

    public static int waveTargets() {
        return waveTargets;
    }

    public static String boss() {
        return boss;
    }

    // Wave metadata stays accurate when lingering lance marks overlap the next wave.
    public static int waveKind() {
        return wavePrimaryKind;
    }

    public static int waveFollowupKind() {
        return waveSecondaryKind;
    }

    public static long waveAge() {
        return System.currentTimeMillis() - waveMs;
    }

    public static long hitAge() {
        return System.currentTimeMillis() - hitMs;
    }

    public static long dodgeAge() {
        return System.currentTimeMillis() - dodgeMs;
    }

    public static long hitWindow() {
        return HIT_MS;
    }

    public static long dodgeWindow() {
        return DODGE_MS;
    }

    public static long waveWindow() {
        return WAVE_MS;
    }

    /** True when the storm is pointed at this client: a mark is close or the local player was hit. */
    public static boolean endangered() {
        LocalPlayer player = Minecraft.getInstance().player;
        if (player == null) {
            return false;
        }
        for (Strike strike : strikes) {
            double dx = player.getX() - strike.rx();
            double dz = player.getZ() - strike.rz();
            if (dx * dx + dz * dz <= strike.radius * strike.radius) {
                return true;
            }
        }
        return hitAge() < HIT_MS;
    }

    /** The boss is spared: the server never marks them, and the banner says so. */
    public static boolean spared() {
        LocalPlayer player = Minecraft.getInstance().player;
        return player != null && !boss.isEmpty()
                && boss.equals(player.getGameProfile().getName()) && waveTargets == 0;
    }

    private static Strike find(int id) {
        for (Strike strike : strikes) {
            if (strike.id == id) {
                return strike;
            }
        }
        return null;
    }

    private static Strike remove(int id) {
        for (Iterator<Strike> it = strikes.iterator(); it.hasNext(); ) {
            Strike strike = it.next();
            if (strike.id == id) {
                it.remove();
                return strike;
            }
        }
        return null;
    }

    /** The server's hit test, run locally the moment the payload lands: only the feel is ours. */
    private static void react(double x, double y, double z, float radius, long now) {
        LocalPlayer player = Minecraft.getInstance().player;
        if (player == null) {
            return;
        }
        double dx = player.getX() - x;
        double dz = player.getZ() - z;
        double dy = player.getY() - y;
        double flat = dx * dx + dz * dz;
        if (Math.abs(dy) <= 4.0 && flat <= radius * radius) {
            hitMs = now;
            dodgeMs = -10000L;
        } else if (now - hitMs >= IMPACT_MS && Math.abs(dy) <= 8.0
                && flat <= radius * 3.0 * radius * 3.0) {
            dodgeMs = now;
        }
    }
}
