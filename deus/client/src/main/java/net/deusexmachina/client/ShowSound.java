package net.deusexmachina.client;

import java.util.concurrent.CompletableFuture;
import net.minecraft.Util;
import net.minecraft.client.resources.sounds.AbstractSoundInstance;
import net.minecraft.client.resources.sounds.Sound;
import net.minecraft.client.resources.sounds.TickableSoundInstance;
import net.minecraft.client.sounds.AudioStream;
import net.minecraft.client.sounds.SoundBufferLibrary;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.RandomSource;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.api.distmarker.OnlyIn;

/**
 * The song as one continuous streaming sound. Volume follows the song slider
 * live; pausing is done by stopping the instance and later starting a new one
 * seeked to the remembered sample, so there is never a chunk gap.
 */
@OnlyIn(Dist.CLIENT)
public final class ShowSound extends AbstractSoundInstance implements TickableSoundInstance {
    public static final ResourceLocation EVENT = ResourceLocation.fromNamespaceAndPath("deusexmachina", "main_track");

    private final long startSample;
    private volatile VorbisStream stream;
    private volatile boolean stopped;

    public ShowSound(long startSample) {
        super(EVENT, SoundSource.RECORDS, RandomSource.create());
        this.startSample = startSample;
        this.attenuation = Attenuation.NONE;
        this.relative = true;
    }

    @Override
    public CompletableFuture<AudioStream> getStream(SoundBufferLibrary soundBuffers, Sound sound, boolean looping) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                VorbisStream vorbis = new VorbisStream(
                    net.minecraft.client.Minecraft.getInstance().getResourceManager(), this.startSample);
                this.stream = vorbis;
                return vorbis;
            } catch (java.io.IOException e) {
                throw new java.util.concurrent.CompletionException(e);
            }
        }, Util.ioPool());
    }

    public VorbisStream stream() {
        return this.stream;
    }

    @Override
    public float getVolume() {
        return MusicVolume.scale();
    }

    @Override
    public boolean canStartSilent() {
        return true;
    }

    @Override
    public boolean isStopped() {
        return this.stopped;
    }

    public void stopSound() {
        this.stopped = true;
    }

    @Override
    public void tick() {
    }
}