package net.deusexmachina.paper;

/** The show's tuning numbers, ported verbatim from the mod's ShowConstants. */
public final class ShowConstants {
    public static final int DROP_TICKS = 219;
    /** Vanilla rain ramps 0.01/tick, so the storm is ordered 104 ticks early to be full at the drop. */
    public static final int RAIN_TICKS = DROP_TICKS - 104;
    public static final int CLOSING_TICKS = 80;
    public static final int BOSS_PHASE2_HP = 50;
    public static final int BOSS_DEATH_LINGER = 40;

    public static final int STORM_FIRST_TICKS = DROP_TICKS + 120;
    public static final int STORM_PERIOD_TICKS = 120;
    public static final int STORM_VOLLEY = 4;
    public static final int STORM_REST_TICKS = 600;
    public static final int STORM_WARN_TICKS = 60;
    public static final int STORM_LOCK_TICKS = 20;
    public static final float STORM_RADIUS = 3.0F;
    public static final float STORM_DAMAGE = 12.0F;
    public static final int STORM_DEBUFF_TICKS = 80;
    public static final int STORM_PHASE2_PERIOD_TICKS = 70;
    public static final int STORM_PHASE2_REST_TICKS = 240;

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

    public static final int LASER_WARN_TICKS = 50;
    public static final float LASER_RADIUS = 2.6F;
    public static final int LASER_VOLLEY = 5;
    public static final int LASER_VOLLEY_P2 = 9;
    public static final float LASER_VOLLEY_RING = 2.3F;
    public static final float LASER_VOLLEY_DAMAGE = 5.0F;
    public static final float LASER_VOLLEY_P2_DAMAGE = 9.0F;
    public static final int LASER_VOLLEY_PERIOD_TICKS = 160;
    public static final int LASER_VOLLEY_P2_PERIOD_TICKS = 300;
    public static final int LASER_FIRST_TICKS = DROP_TICKS + 160;

    public static final int STATE_IDLE = 0;
    public static final int STATE_PLAYING = 1;
    public static final int STATE_PAUSED = 2;
    public static final int STATE_CLOSING = 3;

    private ShowConstants() {}
}