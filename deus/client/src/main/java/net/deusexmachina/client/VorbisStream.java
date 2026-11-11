package net.deusexmachina.client;

import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.IntBuffer;
import java.nio.ShortBuffer;
import javax.sound.sampled.AudioFormat;
import net.minecraft.client.sounds.AudioStream;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.ResourceProvider;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.api.distmarker.OnlyIn;
import org.lwjgl.BufferUtils;
import org.lwjgl.stb.STBVorbis;
import org.lwjgl.stb.STBVorbisInfo;
import org.lwjgl.system.MemoryUtil;

/**
 * Native-speed Vorbis decoder over a cached copy of the song, with instant
 * sample seek. Tracks the position actually heard by the listener (written by
 * the Channel mixin from OpenAL state) so the show timeline can follow it.
 */
@OnlyIn(Dist.CLIENT)
public final class VorbisStream implements AudioStream {
    public static final ResourceLocation TRACK = ResourceLocation.fromNamespaceAndPath("deusexmachina", "sounds/main_track.ogg");

    private static ByteBuffer cachedFile;

    private final long handle;
    private final AudioFormat format;
    private final int channels;
    private final int sampleRate;
    private final ShortBuffer scratch;
    private final java.util.ArrayDeque<Integer> bufferFrameCounts = new java.util.ArrayDeque<>();
    private long framesReturned;

    volatile long heardFrames;
    volatile long heardNanos;
    volatile boolean alPlaying;

    public VorbisStream(ResourceProvider resources, long startSample) throws IOException {
        ByteBuffer file = fileBytes(resources);
        IntBuffer error = BufferUtils.createIntBuffer(1);
        this.handle = STBVorbis.stb_vorbis_open_memory(file, error, null);
        if (this.handle == 0L) {
            throw new IOException("stb_vorbis_open_memory failed: " + error.get(0));
        }
        try (STBVorbisInfo info = STBVorbisInfo.malloc()) {
            STBVorbis.stb_vorbis_get_info(this.handle, info);
            this.channels = info.channels();
            this.sampleRate = info.sample_rate();
        }
        this.format = new AudioFormat(this.sampleRate, 16, this.channels, true, false);
        this.scratch = BufferUtils.createShortBuffer(8192 * this.channels);
        if (startSample > 0L) {
            seek(startSample);
        }
    }

    private static synchronized ByteBuffer fileBytes(ResourceProvider resources) throws IOException {
        if (cachedFile == null) {
            byte[] bytes;
            try (InputStream in = resources.open(TRACK)) {
                bytes = in.readAllBytes();
            }
            cachedFile = MemoryUtil.memAlloc(bytes.length);
            cachedFile.put(bytes).flip();
        }
        return cachedFile;
    }

    public void seek(long sample) {
        int target = (int) Math.max(0L, sample);
        if (!STBVorbis.stb_vorbis_seek_frame(this.handle, target)) {
            return;
        }
        long discard = target - STBVorbis.stb_vorbis_get_sample_offset(this.handle);
        while (discard > 0L) {
            int chunk = (int) Math.min(discard, 8192L);
            this.scratch.clear();
            this.scratch.limit(chunk * this.channels);
            int got = STBVorbis.stb_vorbis_get_samples_short_interleaved(this.handle, this.channels, this.scratch);
            if (got <= 0) {
                break;
            }
            discard -= got;
        }
        this.framesReturned = target;
        this.heardFrames = target;
        this.heardNanos = System.nanoTime();
        this.bufferFrameCounts.clear();
    }

    @Override
    public AudioFormat getFormat() {
        return this.format;
    }

    @Override
    public ByteBuffer read(int size) {
        int framesWanted = size / (2 * this.channels);
        // SoundEngine hands this straight to alBufferData, which reads native memory:
        // a heap ByteBuffer arrives there as a null address and takes the JVM down.
        ByteBuffer out = BufferUtils.createByteBuffer(framesWanted * 2 * this.channels).order(ByteOrder.LITTLE_ENDIAN);
        int done = 0;
        while (done < framesWanted) {
            int chunk = Math.min(framesWanted - done, 8192);
            this.scratch.clear();
            this.scratch.limit(chunk * this.channels);
            int got = STBVorbis.stb_vorbis_get_samples_short_interleaved(this.handle, this.channels, this.scratch);
            if (got <= 0) {
                break;
            }
            this.scratch.position(0);
            this.scratch.limit(got * this.channels);
            for (int i = 0; i < got * this.channels; i++) {
                out.putShort(this.scratch.get(i));
            }
            done += got;
            if (got < chunk) {
                break;
            }
        }
        this.framesReturned += done;
        if (done > 0) {
            this.bufferFrameCounts.addLast(done);
        }
        out.flip();
        return out;
    }

    /**
     * Called from the Channel mixin on the sound executor thread after each
     * pump. Trims the per-buffer frame ledger to the buffers still queued and
     * subtracts what OpenAL has not played yet.
     */
    public void updateHeard(int queuedBuffers, int sampleOffset, boolean playing) {
        while (this.bufferFrameCounts.size() > queuedBuffers) {
            this.bufferFrameCounts.pollFirst();
        }
        long unheard = 0L;
        for (int frames : this.bufferFrameCounts) {
            unheard += frames;
        }
        unheard = Math.max(0L, unheard - sampleOffset);
        this.heardFrames = Math.max(0L, this.framesReturned - unheard);
        this.heardNanos = System.nanoTime();
        this.alPlaying = playing;
    }

    /** Best estimate of the sample currently coming out of the speakers. */
    public long heardPosition() {
        long heard = this.heardFrames;
        if (this.alPlaying) {
            heard += (System.nanoTime() - this.heardNanos) * this.sampleRate / 1_000_000_000L;
        }
        return Math.max(0L, Math.min(heard, this.framesReturned));
    }

    public long framesReturned() {
        return this.framesReturned;
    }

    @Override
    public void close() {
        STBVorbis.stb_vorbis_close(this.handle);
    }
}