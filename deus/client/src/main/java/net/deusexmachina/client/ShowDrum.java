package net.deusexmachina.client;

import java.io.IOException;
import java.io.InputStream;

import net.deusexmachina.ShowConstants;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.api.distmarker.OnlyIn;

/**
 * The song's drum hits, baked to one byte per tick by {@code make_beat.py}. The HUD reads it at the
 * sample actually being heard, so the corner flash lands on the kick rather than on a guessed
 * tempo; a fast attack and a slow release keep it reading as a pulse instead of a strobe.
 */
@OnlyIn(Dist.CLIENT)
public final class ShowDrum {
    private static final ResourceLocation BEAT =
            ResourceLocation.fromNamespaceAndPath("deusexmachina", "show/beat.bin");

    private static byte[] levels;
    private static boolean missing;
    private static float smooth;

    private ShowDrum() {
    }

    /** Smoothed 0..1 drum level for the heard position, decayed when the show is not playing. */
    public static float pulse(float partial) {
        byte[] data = levels();
        if (data == null || data.length == 0
                || ShowClient.state() != ShowConstants.STATE_PLAYING) {
            smooth = 0.0F;
            return 0.0F;
        }
        double tick = ShowClient.position() / (double) ShowConstants.SAMPLES_PER_TICK + partial;
        int i = (int) Math.floor(tick);
        if (i < 0 || i >= data.length) {
            smooth = 0.0F;
            return 0.0F;
        }
        float frac = (float) (tick - i);
        int a = data[i] & 0xFF;
        int b = i + 1 < data.length ? data[i + 1] & 0xFF : a;
        float target = (a + (b - a) * frac) / 255.0F;
        smooth += (target - smooth) * (target > smooth ? 0.55F : 0.12F);
        return Mth.clamp(smooth, 0.0F, 1.0F);
    }

    private static byte[] levels() {
        if (levels == null && !missing) {
            try (InputStream in = Minecraft.getInstance().getResourceManager().open(BEAT)) {
                levels = in.readAllBytes();
            } catch (IOException e) {
                missing = true;
            }
        }
        return levels;
    }
}
