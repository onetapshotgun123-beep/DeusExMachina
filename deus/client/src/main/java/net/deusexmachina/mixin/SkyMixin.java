package net.deusexmachina.mixin;

import net.deusexmachina.client.ShowTimeline;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Tint the sky red during the intro flash only. Outside the flash the vanilla
 * sky colour is returned untouched, so a plain day or night is never reddened.
 */
@Mixin(ClientLevel.class)
public abstract class SkyMixin {
    @Inject(method = "getSkyColor", at = @At("RETURN"), cancellable = true)
    private void deusex$redSky(Vec3 pos, float partialTick, CallbackInfoReturnable<Vec3> cir) {
        float flash = ShowTimeline.skyFlash();
        if (flash > 0.0F) {
            Vec3 base = cir.getReturnValue();
            double r = base.x + (0.85 - base.x) * flash;
            double g = base.y + (0.08 - base.y) * flash;
            double b = base.z + (0.10 - base.z) * flash;
            cir.setReturnValue(new Vec3(r, g, b));
        }
    }
}