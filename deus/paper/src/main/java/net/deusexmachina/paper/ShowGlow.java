package net.deusexmachina.paper;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.entity.Player;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scoreboard.Scoreboard;
import org.bukkit.scoreboard.Team;

/**
 * The mod's player glow, translated to what a vanilla client can draw: the Glowing effect
 * with a scoreboard team colour. The boss burns crimson, a marked player takes the colour of
 * the attack hunting them, everyone else keeps a faint cream outline so the fight stays
 * readable through the storm. Only ambient copies are managed, so a player's own potions are
 * never touched.
 */
public final class ShowGlow {
    private static final String[] MARK_TEAMS = {
            "deusex_bolt", "deusex_grasp", "deusex_siphon", "deusex_barrage",
            "deusex_laser", "deusex_vortex", "deusex_rupture"
    };
    private static final ChatColor[] MARK_COLORS = {
            ChatColor.RED, ChatColor.LIGHT_PURPLE, ChatColor.DARK_RED, ChatColor.YELLOW,
            ChatColor.GOLD, ChatColor.AQUA, ChatColor.WHITE
    };
    private static final String BOSS_TEAM = "deusex_boss";
    private static final String CREW_TEAM = "deusex_crew";

    private final DeusExPlugin plugin;
    private final Map<UUID, String> currentTeam = new HashMap<>();
    private Scoreboard scoreboard;

    public ShowGlow(DeusExPlugin plugin) {
        this.plugin = plugin;
    }

    public void init() {
        scoreboard = Bukkit.getScoreboardManager().getMainScoreboard();
        team(BOSS_TEAM, ChatColor.DARK_RED);
        team(CREW_TEAM, ChatColor.WHITE);
        for (int i = 0; i < MARK_TEAMS.length; i++) {
            team(MARK_TEAMS[i], MARK_COLORS[i]);
        }
    }

    private void team(String name, ChatColor color) {
        Team team = scoreboard.getTeam(name);
        if (team == null) {
            team = scoreboard.registerNewTeam(name);
        }
        team.setColor(color);
        team.setAllowFriendlyFire(true);
        team.setCanSeeFriendlyInvisibles(false);
    }

    /**
     * Refresh the outline on every event participant. The mark colour follows the strike that
     * owns the player right now, preferring a locked one, exactly like the mod's aura tint.
     */
    public void tick(ShowEngine engine) {
        boolean active = engine.state() == ShowConstants.STATE_PLAYING
                || engine.state() == ShowConstants.STATE_PAUSED;
        for (Player player : Bukkit.getOnlinePlayers()) {
            if (!active) {
                drop(player);
                continue;
            }
            if (player.getGameMode() == org.bukkit.GameMode.SPECTATOR) {
                drop(player);
                continue;
            }
            String want;
            if (engine.isBoss(player)) {
                want = BOSS_TEAM;
            } else {
                ShowEngine.Strike mark = engine.markOn(player);
                want = mark != null ? MARK_TEAMS[mark.kind] : CREW_TEAM;
            }
            String have = currentTeam.get(player.getUniqueId());
            if (!want.equals(have)) {
                if (have != null) {
                    Team old = scoreboard.getTeam(have);
                    if (old != null) {
                        old.removeEntry(player.getName());
                    }
                }
                scoreboard.getTeam(want).addEntry(player.getName());
                currentTeam.put(player.getUniqueId(), want);
            }
            buff(player);
        }
    }

    private static void buff(Player player) {
        PotionEffect active = player.getPotionEffect(PotionEffectType.GLOWING);
        if (active != null && active.isAmbient() && active.getDuration() > 20) {
            return;
        }
        player.addPotionEffect(new PotionEffect(PotionEffectType.GLOWING, 40, 0, true, false, true));
    }

    private void drop(Player player) {
        String have = currentTeam.remove(player.getUniqueId());
        if (have != null) {
            Team old = scoreboard.getTeam(have);
            if (old != null) {
                old.removeEntry(player.getName());
            }
        }
        PotionEffect active = player.getPotionEffect(PotionEffectType.GLOWING);
        if (active != null && active.isAmbient()) {
            player.removePotionEffect(PotionEffectType.GLOWING);
        }
    }

    public void shutdown() {
        for (Player player : Bukkit.getOnlinePlayers()) {
            drop(player);
        }
        currentTeam.clear();
    }
}