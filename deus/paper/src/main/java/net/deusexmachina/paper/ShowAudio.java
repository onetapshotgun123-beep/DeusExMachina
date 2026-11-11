package net.deusexmachina.paper;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import org.bukkit.Location;
import org.bukkit.SoundCategory;
import org.bukkit.entity.Player;

/**
 * The chunked music path, ported from the datapack's play_chunk/next_chunk pair. The song is
 * 182 ogg chunks tiling a 60-tick grid (the last is 59), fired at each player on every chunk
 * head. Pause stops the current chunk, resume re-fires it from its head, and a rejoiner is
 * handed the current chunk at once. The intro heartbeat/boom ride on top of the track, on the
 * same ticks the mod fires them.
 */
public final class ShowAudio {
    public static final int CHUNK_TICKS = 60;
    public static final int LAST_CHUNK = 181;
    public static final int LAST_CHUNK_TICKS = 59;
    public static final int TOTAL_TICKS = LAST_CHUNK * CHUNK_TICKS + LAST_CHUNK_TICKS;

    private final DeusExPlugin plugin;
    private final Map<UUID, Integer> volumes = new HashMap<>();
    private int defaultVolume = 45;
    private int lastFiredChunk = -1;

    public ShowAudio(DeusExPlugin plugin) {
        this.plugin = plugin;
    }

    public void setDefaultVolume(int v) {
        defaultVolume = Math.max(0, Math.min(100, v));
    }

    public int volume(Player player) {
        return volumes.getOrDefault(player.getUniqueId(), defaultVolume);
    }

    public void setVolume(Player player, int v) {
        volumes.put(player.getUniqueId(), Math.max(0, Math.min(100, v)));
    }

    public Map<UUID, Integer> volumes() {
        return volumes;
    }

    public void loadVolumes(Map<UUID, Integer> saved) {
        volumes.putAll(saved);
    }

    private float gain(Player player) {
        return volume(player) / 100.0F;
    }

    /** Fire one chunk to one player at their own position; the pack's attenuation makes it global. */
    private void chunk(Player player, int idx) {
        Location at = player.getLocation();
        player.playSound(at, "deusex:chunk_" + idx, SoundCategory.RECORDS, gain(player), 1.0F);
    }

    private void effect(Player player, String sound, float volume, float pitch) {
        player.playSound(player.getLocation(), sound, SoundCategory.RECORDS, volume * gain(player), pitch);
    }

    public void start() {
        lastFiredChunk = 0;
        for (Player player : plugin.getServer().getOnlinePlayers()) {
            chunk(player, 0);
        }
    }

    /** Called every playing tick with the music position. */
    public void tick(int musicTick) {
        if (musicTick > 0 && musicTick % CHUNK_TICKS == 0) {
            int idx = Math.min(musicTick / CHUNK_TICKS, LAST_CHUNK);
            if (idx != lastFiredChunk) {
                lastFiredChunk = idx;
                for (Player player : plugin.getServer().getOnlinePlayers()) {
                    chunk(player, idx);
                }
            }
        }
        for (int beat : ShowData.BEAT_TICKS) {
            if (musicTick == beat) {
                for (Player player : plugin.getServer().getOnlinePlayers()) {
                    effect(player, "deusex:heartbeat", 1.0F, 1.0F);
                }
            }
        }
        if (musicTick == ShowConstants.DROP_TICKS - 7) {
            for (Player player : plugin.getServer().getOnlinePlayers()) {
                effect(player, "deusex:boom_rise", 1.0F, 1.0F);
            }
        }
        if (musicTick == ShowConstants.DROP_TICKS) {
            for (Player player : plugin.getServer().getOnlinePlayers()) {
                player.stopSound("deusex:heartbeat", SoundCategory.RECORDS);
                effect(player, "deusex:boom", 1.0F, 1.0F);
            }
        }
    }

    /** A rejoiner lands on the current chunk at once instead of waiting for the next head. */
    public void catchUp(Player player, int musicTick) {
        chunk(player, Math.min(musicTick / CHUNK_TICKS, LAST_CHUNK));
    }

    public void pause() {
        int idx = Math.max(0, lastFiredChunk);
        for (Player player : plugin.getServer().getOnlinePlayers()) {
            player.stopSound("deusex:chunk_" + idx, SoundCategory.RECORDS);
            player.stopSound("deusex:heartbeat", SoundCategory.RECORDS);
        }
    }

    public void resume(int musicTick) {
        lastFiredChunk = Math.min(musicTick / CHUNK_TICKS, LAST_CHUNK);
        for (Player player : plugin.getServer().getOnlinePlayers()) {
            chunk(player, lastFiredChunk);
        }
    }

    public void stopAll() {
        for (Player player : plugin.getServer().getOnlinePlayers()) {
            player.stopSound(SoundCategory.RECORDS);
        }
        lastFiredChunk = -1;
    }

    /** The once-per-session decode warm-up, 3 s after joining, like the datapack's warm_tick. */
    public void prewarm(Player player) {
        plugin.getServer().getScheduler().runTaskLater(plugin, () -> {
            if (player.isOnline()) {
                player.playSound(player.getLocation(), "deusex:prewarm", SoundCategory.RECORDS, 1.0F, 1.0F);
            }
        }, 60L);
    }
}