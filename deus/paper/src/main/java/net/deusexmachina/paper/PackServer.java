package net.deusexmachina.paper;

import com.sun.net.httpserver.HttpServer;
import java.io.File;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.UUID;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;

/**
 * Serves the embedded resource pack over a tiny built-in HTTP server and pushes it to every
 * joining client with its SHA-1, so the show's fonts and sounds arrive without any manual
 * install. An external pack.url in the config bypasses the built-in server entirely.
 */
public final class PackServer {
    private final DeusExPlugin plugin;
    private final UUID packId = UUID.nameUUIDFromBytes("deusexmachina-pack".getBytes(StandardCharsets.UTF_8));
    private HttpServer server;
    private byte[] sha1 = new byte[0];
    private String url = "";

    public PackServer(DeusExPlugin plugin) {
        this.plugin = plugin;
    }

    public void start(File zip, String host, int port, String externalUrl) {
        try {
            byte[] bytes = Files.readAllBytes(zip.toPath());
            sha1 = MessageDigest.getInstance("SHA-1").digest(bytes);
            if (externalUrl != null && !externalUrl.isBlank()) {
                url = externalUrl;
                plugin.getLogger().info("Resource pack served externally: " + url);
                return;
            }
            server = HttpServer.create(new InetSocketAddress(port), 0);
            server.createContext("/deusex-pack.zip", exchange -> {
                exchange.getResponseHeaders().set("Content-Type", "application/zip");
                exchange.sendResponseHeaders(200, bytes.length);
                try (OutputStream out = exchange.getResponseBody()) {
                    out.write(bytes);
                }
            });
            server.setExecutor(null);
            server.start();
            url = "http://" + host + ":" + port + "/deusex-pack.zip";
            plugin.getLogger().info("Resource pack server listening on port " + port);
        } catch (Exception e) {
            plugin.getLogger().warning("Could not start the resource pack server: " + e);
        }
    }

    public void send(Player player) {
        if (url.isEmpty()) {
            return;
        }
        Component prompt = Component.text(plugin.getConfig().getString("pack.prompt",
                "Deus Ex Machina needs this pack to draw the show."));
        boolean required = plugin.getConfig().getBoolean("pack.required", true);
        player.setResourcePack(packId, url, sha1, prompt, required);
    }

    public String url() {
        return url;
    }

    public void stop() {
        if (server != null) {
            server.stop(0);
            server = null;
        }
    }
}