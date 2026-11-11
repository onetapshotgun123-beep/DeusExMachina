package net.deusexmachina.mixin;

import com.mojang.blaze3d.audio.Channel;
import net.deusexmachina.client.VorbisStream;
import net.minecraft.client.sounds.AudioStream;
import org.lwjgl.openal.AL10;
import org.lwjgl.openal.AL11;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * After each stream pump, read OpenAL's queue state on the sound executor
 * thread (where vanilla already makes AL calls) and tell our stream which
 * sample is actually being heard.
 */
@Mixin(Channel.class)
public abstract class ChannelMixin {
    @Shadow
    private int source;

    @Shadow
    private AudioStream stream;

    @Inject(method = "updateStream", at = @At("TAIL"))
    private void deusex$trackHeard(CallbackInfo ci) {
        if (this.stream instanceof VorbisStream vorbis) {
            int queued = AL10.alGetSourcei(this.source, AL10.AL_BUFFERS_QUEUED);
            int offset = AL10.alGetSourcei(this.source, AL11.AL_SAMPLE_OFFSET);
            int state = AL10.alGetSourcei(this.source, AL10.AL_SOURCE_STATE);
            vorbis.updateHeard(queued, offset, state == AL10.AL_PLAYING);
        }
    }
}