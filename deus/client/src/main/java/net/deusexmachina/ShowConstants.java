package net.deusexmachina;

/**
 * The numbers both halves of the show agree on. TOTAL_SAMPLES and SAMPLE_RATE are enforced against
 * the shipped main_track.ogg by validate_assets.py, so the server clock cannot drift away from the
 * file the clients decode. The tick anchors are the ones the datapack used: the slam lands 10.947 s
 * into the recording (219 ticks) and the storm is ordered on that same tick, so the rain starts the
 * moment the heart bursts instead of arriving early.
 */
public final class ShowConstants {
    public static final int SAMPLE_RATE = 44100;
    public static final long TOTAL_SAMPLES = 24075264L;
    public static final long SAMPLES_PER_TICK = SAMPLE_RATE / 20;
    public static final int DROP_TICKS = 219;
    public static final int RAIN_TICKS = DROP_TICKS;
    public static final int CLOSING_TICKS = 80;
    /** The bar's seal breaks at half health and latches until the target dies. */
    public static final int BOSS_PHASE2_HP = 50;
    /** The bar flatlines this long after the boss dies, then the show shuts down. */
    public static final int BOSS_DEATH_LINGER = 40;

    /**
     * The storm: after the drop, every non-boss player is marked in turn. A warning follows them
     * for {@link #STORM_WARN_TICKS} - {@link #STORM_LOCK_TICKS}, then pins to the ground for the
     * last lock ticks, and the bolt lands on that pinned point. The seal strikes in volleys of
     * {@link #STORM_VOLLEY} waves, then rests long enough that a player can recover.
     */
    public static final int STORM_FIRST_TICKS = DROP_TICKS + 120;
    public static final int STORM_PERIOD_TICKS = 120;
    public static final int STORM_VOLLEY = 4;
    public static final int STORM_REST_TICKS = 600;
    public static final int STORM_WARN_TICKS = 60;
    public static final int STORM_LOCK_TICKS = 20;
    public static final float STORM_RADIUS = 3.0F;
    public static final float STORM_DAMAGE = 12.0F;
    public static final int STORM_DEBUFF_TICKS = 80;
    /** Once the seal breaks the sky answers faster: 70-tick gaps instead of 120, shorter rests. */
    public static final int STORM_PHASE2_PERIOD_TICKS = 70;
    public static final int STORM_PHASE2_REST_TICKS = 240;

    /**
     * Attack kinds, packed into the strike payload's phase byte (kind &lt;&lt; 2 | state). The bolt
     * is the storm itself; the others are the seal's ways of twisting the fight toward its bearer:
     * a binding circle that roots players in place, a blood rite that feeds the boss, a
     * fragmentation of the bolt into a walking barrage, and a lance of light aimed at the body.
     */
    public static final byte STRIKE_BOLT = 0;
    public static final byte STRIKE_GRASP = 1;
    public static final byte STRIKE_SIPHON = 2;
    public static final byte STRIKE_BARRAGE = 3;
    public static final byte STRIKE_LASER = 4;
    public static final byte STRIKE_VORTEX = 5;
    public static final byte STRIKE_RUPTURE = 6;

    public static final int COMBO_DELAY_TICKS = 24;
    public static final int VORTEX_WARN_TICKS = 60;
    public static final float VORTEX_RADIUS = 6.0F;
    public static final float VORTEX_DAMAGE = 6.0F;
    public static final int RUPTURE_WARN_TICKS = 60;
    public static final float RUPTURE_RADIUS = 3.5F;
    public static final float RUPTURE_DAMAGE = 10.0F;

    public static final int GRASP_WARN_TICKS = 50;
    public static final float GRASP_RADIUS = 5.5F;
    public static final float GRASP_DAMAGE = 4.0F;
    public static final int GRASP_DEBUFF_TICKS = 60;
    public static final int SIPHON_WARN_TICKS = 45;
    public static final float SIPHON_RADIUS = 4.5F;
    public static final float SIPHON_DRAIN = 4.0F;
    public static final int SIPHON_BOSS_HEAL = 3;
    public static final int BARRAGE_WARN_TICKS = 60;
    public static final int BARRAGE_SHARDS = 3;
    public static final int BARRAGE_SHARD_DELAY = 8;
    public static final int BARRAGE_SHARD_WARN_TICKS = 16;
    public static final float BARRAGE_SHARD_RADIUS = 2.4F;
    public static final float BARRAGE_SHARD_DAMAGE = 5.0F;
    /** The lance: a beam aimed at the player's chest, not the floor. Step out of its line. */
    public static final int LASER_WARN_TICKS = 50;
    public static final float LASER_RADIUS = 2.6F;

    public static final int LASER_VOLLEY = 5;
    public static final int LASER_VOLLEY_P2 = 9;
    /** Ring radius: smaller than the lance radius, so the centre of the formation is never safe. */
    public static final float LASER_VOLLEY_RING = 2.3F;
    public static final float LASER_VOLLEY_DAMAGE = 5.0F;
    public static final float LASER_VOLLEY_P2_DAMAGE = 9.0F;
    public static final int LASER_VOLLEY_PERIOD_TICKS = 160;
    public static final int LASER_VOLLEY_P2_PERIOD_TICKS = 300;
    public static final int LASER_FIRST_TICKS = DROP_TICKS + 160;

    public static final byte ACT_START = 1;
    public static final byte ACT_SYNC = 2;
    public static final byte ACT_PAUSE = 3;
    public static final byte ACT_STOP = 4;
    public static final byte ACT_CLOSING = 5;
    public static final byte ACT_START_LOOP = 6;
    public static final byte ACT_SYNC_LOOP = 7;

    public static final int STATE_IDLE = 0;
    public static final int STATE_PLAYING = 1;
    public static final int STATE_PAUSED = 2;
    public static final int STATE_CLOSING = 3;

    private ShowConstants() {}

    public static long ticksToSamples(long ticks) {
        return ticks * SAMPLES_PER_TICK;
    }

    public static long samplesToTicks(long samples) {
        return samples / SAMPLES_PER_TICK;
    }
}