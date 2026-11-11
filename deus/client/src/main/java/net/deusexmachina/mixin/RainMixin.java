package net.deusexmachina.mixin;

import com.mojang.blaze3d.vertex.VertexConsumer;
import net.deusexmachina.client.ShowTimeline;
import net.minecraft.client.renderer.LevelRenderer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.Slice;

/**
 * Paint vanilla's rain red while the show is past the drop, and only then.
 * The redirect is sliced to the four rain vertex colours (ordinals 0-3);
 * the snow colours (ordinals 4-7) are left white. Outside the show the
 * original white colour passes through, so natural rain is never blood.
 */
@Mixin(LevelRenderer.class)
public abstract class RainMixin {
    @Redirect(
        method = "renderSnowAndRain",
        slice = @Slice(
            from = @At(value = "INVOKE", target = "Lcom/mojang/blaze3d/vertex/VertexConsumer;setColor(FFFF)Lcom/mojang/blaze3d/vertex/VertexConsumer;", ordinal = 0),
            to = @At(value = "INVOKE", target = "Lcom/mojang/blaze3d/vertex/VertexConsumer;setColor(FFFF)Lcom/mojang/blaze3d/vertex/VertexConsumer;", ordinal = 4)
        ),
        at = @At(value = "INVOKE", target = "Lcom/mojang/blaze3d/vertex/VertexConsumer;setColor(FFFF)Lcom/mojang/blaze3d/vertex/VertexConsumer;")
    )
    private VertexConsumer deusex$redRain(VertexConsumer vc, float r, float g, float b, float a) {
        if (ShowTimeline.rainRed()) {
            return vc.setColor(0.70F, 0.08F, 0.11F, a);
        }
        return vc.setColor(r, g, b, a);
    }
}