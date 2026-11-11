package net.deusexmachina.paper;

import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;

public final class ShowListener implements Listener {
    private final DeusExPlugin plugin;

    public ShowListener(DeusExPlugin plugin) {
        this.plugin = plugin;
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        plugin.engine().onJoin(player);
        plugin.packServer().send(player);
        plugin.audio().prewarm(player);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent event) {
        plugin.engine().onQuit(event.getPlayer());
    }

    @EventHandler
    public void onDeath(PlayerDeathEvent event) {
        plugin.engine().onBossDeath(event.getEntity());
    }
}