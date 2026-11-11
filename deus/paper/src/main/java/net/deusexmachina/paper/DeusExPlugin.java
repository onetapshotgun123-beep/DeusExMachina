package net.deusexmachina.paper;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import io.papermc.paper.datapack.Datapack;
import io.papermc.paper.datapack.DatapackManager;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.command.PluginCommand;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.plugin.java.JavaPlugin;

public final class DeusExPlugin extends JavaPlugin {
    private ShowAudio audio;
    private ShowScreen screen;
    private ShowGlow glow;
    private ShowEngine engine;
    private PackServer packServer;

    public ShowAudio audio() {
        return audio;
    }

    public ShowScreen screen() {
        return screen;
    }

    public ShowGlow glow() {
        return glow;
    }

    public ShowEngine engine() {
        return engine;
    }

    public PackServer packServer() {
        return packServer;
    }

    @Override
    public void onEnable() {
        saveDefaultConfig();
        audio = new ShowAudio(this);
        audio.setDefaultVolume(getConfig().getInt("music.default-volume", 45));
        ConfigurationSection volumes = getConfig().getConfigurationSection("volumes");
        if (volumes != null) {
            Map<UUID, Integer> saved = new HashMap<>();
            for (String key : volumes.getKeys(false)) {
                try {
                    saved.put(UUID.fromString(key), volumes.getInt(key));
                } catch (IllegalArgumentException ignored) {
                }
            }
            audio.loadVolumes(saved);
        }
        screen = new ShowScreen(this);
        glow = new ShowGlow(this);
        glow.init();
        engine = new ShowEngine(this);

        packServer = new PackServer(this);
        File zip = extractPack();
        if (zip != null) {
            packServer.start(zip, getConfig().getString("pack.host", "127.0.0.1"),
                    getConfig().getInt("pack.port", 25599), getConfig().getString("pack.url", ""));
        }
        installAdvancementPack();

        ShowCommands commands = new ShowCommands(this);
        PluginCommand command = getCommand("deusex");
        command.setExecutor(commands);
        command.setTabCompleter(commands);
        getServer().getPluginManager().registerEvents(new ShowListener(this), this);
        getServer().getScheduler().runTaskTimer(this, () -> engine.tick(), 1L, 1L);
        getLogger().info("Deus Ex Machina ready. /deusex start <player> <hp> begins the show.");
    }

    @Override
    public void onDisable() {
        if (engine != null) {
            engine.shutdown();
        }
        if (glow != null) {
            glow.shutdown();
        }
        if (packServer != null) {
            packServer.stop();
        }
        if (audio != null) {
            getConfig().set("volumes", null);
            for (Map.Entry<UUID, Integer> entry : audio.volumes().entrySet()) {
                getConfig().set("volumes." + entry.getKey(), entry.getValue());
            }
            saveConfig();
        }
    }

    private File extractPack() {
        File out = new File(getDataFolder(), "deusex-pack.zip");
        try (InputStream in = getResource("deusex-pack.zip")) {
            if (in == null) {
                getLogger().warning("deusex-pack.zip is missing from the jar; clients will get no pack.");
                return null;
            }
            getDataFolder().mkdirs();
            Files.copy(in, out.toPath(), StandardCopyOption.REPLACE_EXISTING);
            return out;
        } catch (IOException e) {
            getLogger().warning("Could not extract the resource pack: " + e);
            return null;
        }
    }

    /** The victory advancement ships as a tiny world datapack so vanilla clients can earn it. */
    private void installAdvancementPack() {
        World world = Bukkit.getWorlds().get(0);
        File dir = new File(world.getWorldFolder(), "datapacks/deusexmachina");
        try {
            copyResource("datapack/pack.mcmeta", new File(dir, "pack.mcmeta"));
            copyResource("datapack/data/deusexmachina/advancement/server_free.json",
                    new File(dir, "data/deusexmachina/advancement/server_free.json"));
        } catch (IOException e) {
            getLogger().warning("Could not install the advancement datapack: " + e);
            return;
        }
        DatapackManager manager = getServer().getDatapackManager();
        manager.refreshPacks();
        for (Datapack pack : manager.getPacks()) {
            if (pack.getName().endsWith("deusexmachina")) {
                if (!pack.isEnabled()) {
                    pack.setEnabled(true);
                }
                return;
            }
        }
        getLogger().warning("Advancement datapack was not discovered; the victory reward will not fire.");
    }

    private void copyResource(String path, File out) throws IOException {
        try (InputStream in = getResource(path)) {
            if (in == null) {
                throw new IOException("missing jar resource " + path);
            }
            out.getParentFile().mkdirs();
            Files.copy(in, out.toPath(), StandardCopyOption.REPLACE_EXISTING);
        }
    }
}