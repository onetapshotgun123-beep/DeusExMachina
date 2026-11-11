package net.deusexmachina.paper;

import java.util.ArrayList;
import java.util.List;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;

public final class ShowCommands implements CommandExecutor, TabCompleter {
    private final DeusExPlugin plugin;

    public ShowCommands(DeusExPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0) {
            usage(sender);
            return true;
        }
        switch (args[0].toLowerCase()) {
            case "start" -> {
                if (!require(sender, "deusex.use")) {
                    return true;
                }
                if (args.length < 3) {
                    sender.sendMessage(Component.text("Usage: /deusex start <player> <hp 1-100>", NamedTextColor.RED));
                    return true;
                }
                Player target = Bukkit.getPlayerExact(args[1]);
                if (target == null) {
                    sender.sendMessage(Component.text("Player not online: " + args[1], NamedTextColor.RED));
                    return true;
                }
                int hp;
                try {
                    hp = Integer.parseInt(args[2]);
                } catch (NumberFormatException e) {
                    sender.sendMessage(Component.text("HP must be a number 1-100.", NamedTextColor.RED));
                    return true;
                }
                if (hp < 1 || hp > 100) {
                    sender.sendMessage(Component.text("HP must be 1-100.", NamedTextColor.RED));
                    return true;
                }
                plugin.engine().startWithBoss(target, hp);
                sender.sendMessage(Component.text("Show started. RONOVA bears " + target.getName()
                        + " with " + hp + " HP.", NamedTextColor.GREEN));
            }
            case "pause" -> {
                if (require(sender, "deusex.use")) {
                    plugin.engine().pause();
                    sender.sendMessage(Component.text("Show paused.", NamedTextColor.GREEN));
                }
            }
            case "resume" -> {
                if (require(sender, "deusex.use")) {
                    plugin.engine().resume();
                    sender.sendMessage(Component.text("Show resumed.", NamedTextColor.GREEN));
                }
            }
            case "stop" -> {
                if (require(sender, "deusex.use")) {
                    plugin.engine().stop();
                    sender.sendMessage(Component.text("Show stopping.", NamedTextColor.GREEN));
                }
            }
            case "loop" -> {
                if (require(sender, "deusex.use")) {
                    plugin.engine().toggleLoop();
                }
            }
            case "reset" -> {
                if (require(sender, "deusex.admin")) {
                    plugin.engine().resetAll();
                    sender.sendMessage(Component.text("Event reset.", NamedTextColor.GREEN));
                }
            }
            case "phase2" -> {
                if (require(sender, "deusex.admin")) {
                    plugin.engine().commandPhase2(sender);
                }
            }
            case "volume" -> {
                if (!require(sender, "deusex.volume")) {
                    return true;
                }
                if (!(sender instanceof Player player)) {
                    sender.sendMessage(Component.text("Only players can set their volume.", NamedTextColor.RED));
                    return true;
                }
                if (args.length < 2) {
                    sender.sendMessage(Component.text("Your music volume: "
                            + plugin.audio().volume(player) + " (use /deusex volume <0-100>)", NamedTextColor.GREEN));
                    return true;
                }
                int v;
                try {
                    v = Integer.parseInt(args[1]);
                } catch (NumberFormatException e) {
                    sender.sendMessage(Component.text("Volume must be 0-100.", NamedTextColor.RED));
                    return true;
                }
                plugin.audio().setVolume(player, v);
                sender.sendMessage(Component.text("Music volume set to " + plugin.audio().volume(player)
                        + ". Applies from the next music chunk.", NamedTextColor.GREEN));
            }
            case "status" -> {
                if (require(sender, "deusex.use")) {
                    for (String line : plugin.engine().status()) {
                        sender.sendMessage(Component.text(line, NamedTextColor.GRAY));
                    }
                }
            }
            default -> usage(sender);
        }
        return true;
    }

    private static boolean require(CommandSender sender, String permission) {
        if (!sender.hasPermission(permission)) {
            sender.sendMessage(Component.text("You lack " + permission + ".", NamedTextColor.RED));
            return false;
        }
        return true;
    }

    private static void usage(CommandSender sender) {
        sender.sendMessage(Component.text(
                "/deusex start <player> <hp> | pause | resume | stop | loop | status", NamedTextColor.GRAY));
        sender.sendMessage(Component.text(
                "/deusex reset | phase2 (admin)   /deusex volume <0-100> (self)", NamedTextColor.GRAY));
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        List<String> out = new ArrayList<>();
        if (args.length == 1) {
            for (String sub : new String[] {"start", "pause", "resume", "stop", "loop", "status", "volume"}) {
                if (sub.startsWith(args[0].toLowerCase())) {
                    out.add(sub);
                }
            }
            if (sender.hasPermission("deusex.admin")) {
                for (String sub : new String[] {"reset", "phase2"}) {
                    if (sub.startsWith(args[0].toLowerCase())) {
                        out.add(sub);
                    }
                }
            }
        } else if (args.length == 2 && args[0].equalsIgnoreCase("start")) {
            for (Player player : Bukkit.getOnlinePlayers()) {
                if (player.getName().toLowerCase().startsWith(args[1].toLowerCase())) {
                    out.add(player.getName());
                }
            }
        } else if (args.length == 3 && args[0].equalsIgnoreCase("start")) {
            out.add("100");
        } else if (args.length == 2 && args[0].equalsIgnoreCase("volume")) {
            out.add("45");
            out.add("100");
            out.add("0");
        }
        return out;
    }
}