package net.deusexmachina.client;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;

import net.deusexmachina.ShowConstants;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.AbstractClientPlayer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.api.distmarker.OnlyIn;
import net.neoforged.neoforge.client.event.RenderLevelStageEvent;

import org.joml.Matrix4f;

/**
 * The event's answer to the red wash: every player carries a small additive aura so bodies stay
 * readable through the tint. The boss burns crimson, a player standing under a mark glows in the
 * colour of the attack coming for them, everyone else keeps a faint cream ember. A glint band
 * sweeps each body on a slow clock and a few motes rise off the shoulders - the same living-sheen
 * idea as the boss bar, moved onto the players so eyes find people instead of overlays.
 *
 * <p>Drawn in the lightning render type (additive, no texture) at AFTER_PARTICLES, so the glow
 * lights the player without ever writing a solid panel over the view.
 */
@OnlyIn(Dist.CLIENT)
public final class ShowGlow {
    private static final double RANGE = 40.0;
    private static final double FADE_START = 24.0;

    private ShowGlow() {
    }

    public static void renderWorld(RenderLevelStageEvent event) {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_PARTICLES) {
            return;
        }
        int state = ShowClient.state();
        if (state != ShowConstants.STATE_PLAYING && state != ShowConstants.STATE_PAUSED) {
            return;
        }
        Minecraft mc = Minecraft.getInstance();
        if (mc.level == null || mc.player == null) {
            return;
        }
        Camera camera = event.getCamera();
        Vec3 at = camera.getPosition();
        PoseStack pose = event.getPoseStack();
        MultiBufferSource.BufferSource buffers = mc.renderBuffers().bufferSource();
        VertexConsumer vc = buffers.getBuffer(RenderType.lightning());
        long now = System.currentTimeMillis();
        String bossName = ShowBoss.visible() ? ShowBoss.target() : "";
        for (AbstractClientPlayer player : mc.level.players()) {
            // In first person the local body is the camera; an aura on it would fill the screen.
            if (player == mc.player && mc.options.getCameraType().isFirstPerson()) {
                continue;
            }
            double dx = player.getX() - at.x;
            double dy = player.getY() - at.y;
            double dz = player.getZ() - at.z;
            double dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
            if (dist > RANGE) {
                continue;
            }
            float fade = dist <= FADE_START ? 1.0F
                    : (float) (1.0 - (dist - FADE_START) / (RANGE - FADE_START));
            boolean boss = !bossName.isEmpty() && player.getName().getString().equals(bossName);
            ShowStrike.Strike mark = markedStrike(player);
            float[] color;
            float strength;
            if (boss) {
                color = new float[] {1.0F, 0.12F, 0.10F};
                strength = 0.34F;
            } else if (mark != null) {
                color = mark.locked() ? ShowStrikeRender.lockColor(mark.kind)
                        : ShowStrikeRender.trackColor(mark.kind);
                strength = 0.30F;
            } else {
                color = new float[] {1.0F, 0.85F, 0.60F};
                strength = 0.14F;
            }
            float pulse = boss || mark != null
                    ? 0.75F + 0.25F * Mth.sin(now * 0.006F)
                    : 0.85F + 0.15F * Mth.sin(now * 0.002F + player.getId());
            double px = player.getX();
            double py = player.getY();
            double pz = player.getZ();
            aura(pose, vc, px, py, pz, at, color, strength * fade * pulse, boss ? 1.15F : 0.95F);
            glint(pose, vc, px, py, pz, at, color, strength * fade, now);
            motes(pose, vc, px, py, pz, at, color, strength * fade * 0.8F, now);
        }
        buffers.endBatch(RenderType.lightning());
    }

    /** The strike whose mark currently covers this player, preferring a sealed one. */
    private static ShowStrike.Strike markedStrike(AbstractClientPlayer player) {
        ShowStrike.Strike best = null;
        for (ShowStrike.Strike strike : ShowStrike.strikes()) {
            double dx = player.getX() - strike.rx();
            double dz = player.getZ() - strike.rz();
            double reach = strike.radius + 0.5;
            if (dx * dx + dz * dz <= reach * reach && Math.abs(player.getY() - strike.ry()) <= 4.0) {
                if (best == null || strike.locked()) {
                    best = strike;
                }
            }
        }
        return best;
    }

    /** A camera-facing radial fan: bright at the body, fading to nothing at the rim. */
    private static void aura(PoseStack pose, VertexConsumer vc,
                             double px, double py, double pz, Vec3 at,
                             float[] color, float alpha, float radius) {
        if (alpha <= 0.004F) {
            return;
        }
        double cy = py + 0.9;
        double fx = at.x - px;
        double fy = at.y - cy;
        double fz = at.z - pz;
        double fl = Math.sqrt(fx * fx + fy * fy + fz * fz);
        if (fl < 1.0E-4) {
            return;
        }
        fx /= fl;
        fy /= fl;
        fz /= fl;
        double rl = Math.sqrt(fx * fx + fz * fz);
        if (rl < 1.0E-4) {
            return;
        }
        double rx = fz / rl;
        double rz = -fx / rl;
        double ux = fy * rz;
        double uy = fz * rx - fx * rz;
        double uz = -fy * rx;
        pose.pushPose();
        pose.translate(px - at.x, cy - at.y, pz - at.z);
        Matrix4f m = pose.last().pose();
        int n = 16;
        for (int i = 0; i < n; i++) {
            double a0 = Math.PI * 2.0 * i / n;
            double a1 = Math.PI * 2.0 * (i + 1) / n;
            float x0 = (float) ((rx * Math.cos(a0) + ux * Math.sin(a0)) * radius);
            float y0 = (float) ((uy * Math.sin(a0)) * radius);
            float z0 = (float) ((rz * Math.cos(a0) + uz * Math.sin(a0)) * radius);
            float x1 = (float) ((rx * Math.cos(a1) + ux * Math.sin(a1)) * radius);
            float y1 = (float) ((uy * Math.sin(a1)) * radius);
            float z1 = (float) ((rz * Math.cos(a1) + uz * Math.sin(a1)) * radius);
            fanQuad(m, vc, x0, y0, z0, x1, y1, z1, color[0], color[1], color[2], alpha);
        }
        pose.popPose();
    }

    /** One wedge of the aura, both windings so it shows from either side. */
    private static void fanQuad(Matrix4f m, VertexConsumer vc,
                                float x0, float y0, float z0, float x1, float y1, float z1,
                                float r, float g, float b, float alpha) {
        vc.addVertex(m, 0.0F, 0.0F, 0.0F).setColor(r, g, b, alpha);
        vc.addVertex(m, x0, y0, z0).setColor(r, g, b, 0.0F);
        vc.addVertex(m, x1, y1, z1).setColor(r, g, b, 0.0F);
        vc.addVertex(m, x1, y1, z1).setColor(r, g, b, 0.0F);
        vc.addVertex(m, 0.0F, 0.0F, 0.0F).setColor(r, g, b, alpha);
        vc.addVertex(m, x1, y1, z1).setColor(r, g, b, 0.0F);
        vc.addVertex(m, x0, y0, z0).setColor(r, g, b, 0.0F);
        vc.addVertex(m, x0, y0, z0).setColor(r, g, b, 0.0F);
    }

    /** The enchanted-glint idea on a body: a bright band sweeps across once every 1.6 s. */
    private static void glint(PoseStack pose, VertexConsumer vc,
                              double px, double py, double pz, Vec3 at,
                              float[] color, float strength, long now) {
        float cycle = (now % 1600L) / 1600.0F;
        float shine = Mth.sin(cycle * (float) Math.PI);
        float alpha = strength * 0.9F * shine;
        if (alpha <= 0.004F) {
            return;
        }
        double fx = at.x - px;
        double fz = at.z - pz;
        double rl = Math.sqrt(fx * fx + fz * fz);
        if (rl < 1.0E-4) {
            return;
        }
        double rx = fz / rl;
        double rz = -fx / rl;
        float sweep = (cycle * 2.0F - 1.0F) * 0.45F;
        pose.pushPose();
        pose.translate(px - at.x + rx * sweep, py - at.y, pz - at.z + rz * sweep);
        Matrix4f m = pose.last().pose();
        float hw = 0.09F;
        float x0 = (float) (-rx * hw);
        float z0 = (float) (-rz * hw);
        float x1 = (float) (rx * hw);
        float z1 = (float) (rz * hw);
        panel(m, vc, x0, 0.05F, z0, x1, 1.85F, z1,
                color[0] * 0.5F + 0.5F, color[1] * 0.5F + 0.5F, color[2] * 0.5F + 0.5F, alpha);
        panel(m, vc, x0 * 0.4F, 0.05F, z0 * 0.4F, x1 * 0.4F, 1.85F, z1 * 0.4F,
                1.0F, 0.98F, 0.92F, Math.min(0.85F, alpha * 1.3F));
        pose.popPose();
    }

    /** Three embers climbing off the body, fading as they rise. */
    private static void motes(PoseStack pose, VertexConsumer vc,
                              double px, double py, double pz, Vec3 at,
                              float[] color, float alpha, long now) {
        if (alpha <= 0.004F) {
            return;
        }
        double fx = at.x - px;
        double fz = at.z - pz;
        double rl = Math.sqrt(fx * fx + fz * fz);
        if (rl < 1.0E-4) {
            return;
        }
        double rx = fz / rl;
        double rz = -fx / rl;
        pose.pushPose();
        pose.translate(px - at.x, py - at.y, pz - at.z);
        Matrix4f m = pose.last().pose();
        for (int i = 0; i < 3; i++) {
            float t = (now * 0.0004F + i / 3.0F) % 1.0F;
            double angle = i * 2.094 + now * 0.0005;
            float ox = (float) (Math.cos(angle) * 0.5);
            float oz = (float) (Math.sin(angle) * 0.5);
            float y = 0.3F + t * 1.9F;
            float a = alpha * (1.0F - t);
            float s = 0.05F;
            float x0 = (float) (ox - rx * s);
            float z0 = (float) (oz - rz * s);
            float x1 = (float) (ox + rx * s);
            float z1 = (float) (oz + rz * s);
            panel(m, vc, x0, y - s, z0, x1, y + s, z1, color[0], color[1], color[2], a);
        }
        pose.popPose();
    }

    /** A camera-facing vertical quad, both windings, uniform colour. */
    private static void panel(Matrix4f m, VertexConsumer vc,
                              float x0, float y0, float z0, float x1, float y1, float z1,
                              float r, float g, float b, float a) {
        if (a <= 0.004F) {
            return;
        }
        vc.addVertex(m, x0, y0, z0).setColor(r, g, b, a);
        vc.addVertex(m, x1, y0, z1).setColor(r, g, b, a);
        vc.addVertex(m, x1, y1, z1).setColor(r, g, b, a);
        vc.addVertex(m, x0, y1, z0).setColor(r, g, b, a);
        vc.addVertex(m, x0, y1, z0).setColor(r, g, b, a);
        vc.addVertex(m, x1, y1, z1).setColor(r, g, b, a);
        vc.addVertex(m, x1, y0, z1).setColor(r, g, b, a);
        vc.addVertex(m, x0, y0, z0).setColor(r, g, b, a);
    }
}