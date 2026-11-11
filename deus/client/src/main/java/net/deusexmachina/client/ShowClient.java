package net.deusexmachina.client;

import net.deusexmachina.ShowConstants;
import net.deusexmachina.net.ShowPositionPayload;
import net.deusexmachina.net.ShowStatePayload;
import net.minecraft.client.Minecraft;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.api.distmarker.OnlyIn;
import net.neoforged.neoforge.network.PacketDistributor;

/**
 * Client half of the show. Owns the one continuous song instance and reports
 * the heard sample back to the server so its clock stays anchored to what the
 * player actually hears. The timeline and all visuals read {@link #position()}.
 */
@OnlyIn(Dist.CLIENT)
public final class ShowClient {
    private static int state = ShowConstants.STATE_IDLE;
    private static boolean loop;
    private static ShowSound sound;
    private static long pausedSamples;
    private static long fallbackSamples;
    private static int reportTicker;
    private static int noStreamTicks;
    private static long lastHeard = -1L;
    private static int stallTicks;
    private static int watchdogRestarts;

    private ShowClient() {
    }

    public static void handle(ShowStatePayload payload) {
        switch (payload.action()) {
            case ShowConstants.ACT_START -> {
                watchdogRestarts = 0;
                ShowStrike.reset();
                startAt(payload.position(), false);
            }
            case ShowConstants.ACT_START_LOOP -> {
                watchdogRestarts = 0;
                ShowStrike.reset();
                startAt(payload.position(), true);
            }
            case ShowConstants.ACT_SYNC -> sync(payload.position(), false);
            case ShowConstants.ACT_SYNC_LOOP -> sync(payload.position(), true);
            case ShowConstants.ACT_PAUSE -> {
                pausedSamples = position();
                stopSound();
                state = ShowConstants.STATE_PAUSED;
                report(pausedSamples);
            }
            case ShowConstants.ACT_CLOSING -> {
                stopSound();
                fallbackSamples = payload.position();
                state = ShowConstants.STATE_CLOSING;
                ShowStrike.reset();
            }
            case ShowConstants.ACT_STOP -> {
                stopSound();
                pausedSamples = 0L;
                fallbackSamples = 0L;
                watchdogRestarts = 0;
                state = ShowConstants.STATE_IDLE;
                ShowStrike.reset();
            }
            default -> {
            }
        }
    }

    private static void startAt(long sample, boolean looping) {
        stopSound();
        state = ShowConstants.STATE_PLAYING;
        loop = looping;
        fallbackSamples = sample;
        noStreamTicks = 0;
        lastHeard = sample;
        stallTicks = 0;
        sound = new ShowSound(sample);
        Minecraft.getInstance().getSoundManager().play(sound);
    }

    private static void sync(long sample, boolean looping) {
        VorbisStream stream = sound != null ? sound.stream() : null;
        if (state == ShowConstants.STATE_PLAYING && stream != null
                && Math.abs(stream.heardPosition() - sample) < ShowConstants.SAMPLES_PER_TICK * 2L) {
            loop = looping;
            fallbackSamples = sample;
            return;
        }
        startAt(sample, looping);
    }

    private static void stopSound() {
        if (sound != null) {
            sound.stopSound();
            Minecraft.getInstance().getSoundManager().stop(sound);
            sound = null;
        }
    }

    /**
     * Sample the timeline should follow. Normally this is what is heard, not what is decoded, but
     * if the audio pump stalls the fallback clock keeps the show moving so the HUD timer, lyrics
     * and rain gate never freeze. See {@link #tick()}.
     */
    public static long position() {
        if (state == ShowConstants.STATE_PLAYING) {
            VorbisStream stream = sound != null ? sound.stream() : null;
            if (stream != null && stallTicks == 0) {
                return stream.heardPosition();
            }
            return fallbackSamples;
        }
        if (state == ShowConstants.STATE_PAUSED) {
            return pausedSamples;
        }
        return fallbackSamples;
    }

    public static int state() {
        return state;
    }

    public static boolean loop() {
        return loop;
    }

    /** How many times the stall watchdog has had to restart the song this show (dev diagnostics). */
    public static int watchdogRestarts() {
        return watchdogRestarts;
    }

    /** One-line snapshot of the audio path for the dev probe's failsafe dump. */
    public static String debugAudio() {
        VorbisStream stream = sound != null ? sound.stream() : null;
        if (stream == null) {
            return "stream=null soundPresent=" + (sound != null) + " noStreamTicks=" + noStreamTicks
                    + " fallback=" + fallbackSamples;
        }
        return "heard=" + stream.heardPosition() + " decoded=" + stream.framesReturned()
                + " alPlaying=" + stream.alPlaying + " stallTicks=" + stallTicks
                + " restarts=" + watchdogRestarts + " fallback=" + fallbackSamples;
    }

    public static void tick() {
        if (state != ShowConstants.STATE_PLAYING) {
            return;
        }
        reportTicker++;
        VorbisStream stream = sound != null ? sound.stream() : null;
        if (stream == null) {
            // The async stream load is still in flight, or the engine skipped playback outright
            // (master volume 0). After a grace period, run the show on the tick clock so it never
            // freezes for muted players or while the decoder warms up.
            if (++noStreamTicks > 40) {
                fallbackSamples = Math.min(fallbackSamples + ShowConstants.SAMPLES_PER_TICK,
                        ShowConstants.TOTAL_SAMPLES);
                if (reportTicker % 20 == 0) {
                    report(fallbackSamples);
                }
            }
            return;
        }
        noStreamTicks = 0;
        long heard = stream.heardPosition();
        long pos;
        if (heard > lastHeard) {
            // Healthy: anchor the fallback clock to what is actually heard.
            lastHeard = heard;
            stallTicks = 0;
            fallbackSamples = heard;
            pos = heard;
        } else {
            // The stream exists but the heard clock stopped: vanilla's pump stalled (a rejoin
            // race, a device hiccup, or a zeroed category volume killed the channel). Keep the
            // show moving on the tick clock and restart the song from where we are to recover
            // the audio, instead of freezing the HUD timer and lyrics forever.
            fallbackSamples = Math.min(fallbackSamples + ShowConstants.SAMPLES_PER_TICK,
                    ShowConstants.TOTAL_SAMPLES);
            pos = fallbackSamples;
            if (++stallTicks > 60) {
                watchdogRestarts++;
                startAt(fallbackSamples, loop);
                return;
            }
        }
        if (reportTicker % 20 == 0 || pos >= ShowConstants.TOTAL_SAMPLES - ShowConstants.SAMPLES_PER_TICK) {
            report(pos);
        }
    }

    private static void report(long samples) {
        if (Minecraft.getInstance().getConnection() != null) {
            PacketDistributor.sendToServer(new ShowPositionPayload(samples));
        }
    }
}