package net.deusexmachina.client;

import java.util.List;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;

import net.deusexmachina.ShowConstants;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.phys.Vec3;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.api.distmarker.OnlyIn;
import net.neoforged.neoforge.client.event.RenderLevelStageEvent;

import org.joml.Matrix4f;
import org.joml.Vector4f;

/**
 * Draws the storm's warning: the supplied sigil laid on the ground where the bolt will fall, and
 * the same mark projected onto the HUD so the player can find it without turning around. The seal
 * lance is the exception: its mark floats at the player's chest and a beam leans down onto it out
 * of the sky, because that attack is aimed at a body, not a patch of ground.
 *
 * <p>The ground pass runs at AFTER_PARTICLES on the level's pose stack. That stack carries
 * camera-relative world coordinates, so the quad is authored in world axes and the camera rotation
 * already applied by the level renderer maps it into view space. The HUD pass projects the mark
 * through the exact matrices of the last frame, so both marks agree pixel for pixel.
 */
@OnlyIn(Dist.CLIENT)
public final class ShowStrikeRender {
    private static final ResourceLocation SIGIL =
            ResourceLocation.fromNamespaceAndPath("deusexmachina", "textures/show/strike_sigils.png");
    private static final int SIGIL_TEX = 512;
    private static final int SIGIL_CELLS = 7;
    private static final int EDGE = 34;
    /**
     * Warnings are hints, not walls: every warning-only layer is drawn at half strength so the
     * world and the players behind it stay readable. Impacts keep their full brightness - the
     * moment something actually lands is the moment it is allowed to shout.
     */
    private static final float WARN_DIM = 0.5F;
    /** Where the lance hangs from: far enough back that the beam leans, high enough to fall. */
    private static final double BEAM_DISTANCE = 46.0;
    private static final double BEAM_HEIGHT = 34.0;

    private static final Matrix4f VIEW = new Matrix4f();
    private static final Matrix4f PROJ = new Matrix4f();
    private static final Vector4f POINT = new Vector4f();
    private static final float[] NDC = new float[2];
    private static boolean haveMatrices;
    private static double camX;
    private static double camY;
    private static double camZ;

    private ShowStrikeRender() {
    }

    // ------------------------------------------------------------------ world pass

    public static void renderWorld(RenderLevelStageEvent event) {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_PARTICLES) {
            return;
        }
        if (!ShowStrike.active()) {
            return;
        }
        Minecraft mc = Minecraft.getInstance();
        if (mc.level == null) {
            return;
        }
        Camera camera = event.getCamera();
        Vec3 at = camera.getPosition();
        camX = at.x;
        camY = at.y;
        camZ = at.z;
        VIEW.set(event.getModelViewMatrix());
        PROJ.set(event.getProjectionMatrix());
        haveMatrices = true;

        PoseStack pose = event.getPoseStack();
        MultiBufferSource.BufferSource buffers = mc.renderBuffers().bufferSource();
        RenderType type = RenderType.entityTranslucentEmissive(SIGIL);
        VertexConsumer vc = buffers.getBuffer(type);
        float smooth = (float) (ShowClient.position() / (double) ShowConstants.SAMPLES_PER_TICK)
                + event.getPartialTick().getGameTimeDeltaPartialTick(true);

        for (ShowStrike.Strike strike : ShowStrike.strikes()) {
            double x = strike.rx();
            double y = strike.ry();
            double z = strike.rz();
            boolean locked = strike.locked();
            float pulse = 0.5F + 0.5F * Mth.sin(smooth * (locked ? 1.35F : 0.5F));
            float[] tint = locked ? lockColor(strike.kind) : trackColor(strike.kind);
            pose.pushPose();
            pose.translate(x - camX, y - camY + (strike.laser() ? 0.0 : 0.035), z - camZ);
            if (strike.laser()) {
                // Aimed at the body: the mark hangs in the air as a crossed glyph instead of a
                // floor decal, so it reads as "this line, not this patch of ground".
                laserMark(pose, vc, strike, smooth, pulse);
            } else if (strike.vortex()) {
                float alpha = ((locked ? 0.7F : 0.4F) + 0.2F * pulse) * WARN_DIM;
                float cycle = smooth * 0.025F;
                float inward = 1.0F - (cycle - (float) Math.floor(cycle));
                sigil(pose, vc, strike.kind, strike.radius, smooth * -3.0F,
                        tint[0], tint[1], tint[2], alpha);
                sigil(pose, vc, strike.kind, strike.radius * (0.15F + inward * 0.7F), smooth * -5.0F,
                        tint[0], tint[1], tint[2], alpha * inward * 0.55F);
            } else if (strike.rupture()) {
                float alpha = ((locked ? 0.65F : 0.4F) + 0.25F * pulse) * WARN_DIM;
                sigil(pose, vc, strike.kind, strike.radius, 0.0F,
                        tint[0], tint[1], tint[2], alpha);
                if (locked) {
                    sigil(pose, vc, strike.kind, strike.radius * (0.96F + pulse * 0.04F), 0.0F,
                            1.0F, 0.62F, 0.14F, 0.35F * pulse * WARN_DIM);
                }
            } else if (locked) {
                // Sealed: the ring snaps to the kind's warning colour, shivers, and a bright bloom
                // rushes outward.
                float urgency = strike.urgency();
                float alpha = (0.55F + 0.45F * pulse) * WARN_DIM;
                sigil(pose, vc, strike.kind, strike.radius * 1.12F, smooth * -2.6F,
                        tint[0] * 0.8F, tint[1] * 0.5F, tint[2] * 0.5F, alpha * 0.8F);
                sigil(pose, vc, strike.kind, strike.radius * 0.88F, smooth * 4.2F,
                        tint[0], tint[1], tint[2], alpha);
                sigil(pose, vc, strike.kind, strike.radius * (1.0F + 0.55F * urgency), smooth * -6.0F,
                        tint[0], tint[1] * 0.5F + 0.45F, tint[2] * 0.5F + 0.35F,
                        0.22F * pulse * (1.0F - urgency * 0.5F) * WARN_DIM);
            } else {
                float alpha = (0.30F + 0.22F * pulse) * WARN_DIM;
                sigil(pose, vc, strike.kind, strike.radius * 1.05F, smooth * 1.1F,
                        tint[0], tint[1], tint[2], alpha);
                sigil(pose, vc, strike.kind, strike.radius * 0.80F, smooth * -1.5F, 1.0F, 1.0F, 1.0F, alpha * 0.55F);
            }
            pose.popPose();
        }

        for (ShowStrike.Impact impact : ShowStrike.impacts()) {
            float life = impact.life();
            float grow = impact.vortex() ? 0.12F + 0.88F * life
                    : impact.rupture() ? 1.0F + (1.0F - life) * 0.25F
                    : 1.0F + (1.0F - life) * 1.8F;
            float[] tint = impactColor(impact.kind);
            pose.pushPose();
            pose.translate(impact.x - camX, impact.y - camY + 0.045, impact.z - camZ);
            sigil(pose, vc, impact.kind, impact.radius * grow, smooth * 7.0F,
                    tint[0], tint[1] * 0.7F + 0.2F, tint[2] * 0.7F + 0.1F, life * 0.55F);
            sigil(pose, vc, impact.kind, impact.radius * grow * 1.35F, smooth * -5.0F,
                    tint[0], tint[1] * 0.35F, tint[2] * 0.30F, life * life * 0.45F);
            pose.popPose();
        }
        buffers.endBatch(type);

        renderFx(pose, buffers, smooth);
    }

    /**
     * The lance's mark: the sigil stood upright at the chest point, one copy turned to face the
     * camera and a second across it, so the glyph is never seen edge-on.
     */
    private static void laserMark(PoseStack pose, VertexConsumer vc, ShowStrike.Strike strike,
                                  float smooth, float pulse) {
        boolean locked = strike.locked();
        float urgency = strike.urgency();
        float[] tint = locked ? lockColor(strike.kind) : trackColor(strike.kind);
        float alpha = (locked ? 0.62F + 0.38F * pulse : 0.34F + 0.24F * pulse) * WARN_DIM;
        float size = strike.radius * (locked ? 0.95F : 0.72F + 0.30F * urgency);
        float face = (float) Math.toDegrees(Math.atan2(strike.rx() - camX, strike.rz() - camZ));
        upright(pose, vc, strike.kind, size, face + smooth * (locked ? -3.2F : 1.5F),
                tint[0], tint[1], tint[2], alpha);
        upright(pose, vc, strike.kind, size * 0.96F, face + 90.0F + smooth * (locked ? 3.2F : -1.5F),
                tint[0] * 0.7F, tint[1] * 0.7F + 0.3F, tint[2] * 0.7F, alpha * 0.55F);
        upright(pose, vc, strike.kind, size * 0.52F, face - smooth * (locked ? 6.0F : 2.4F),
                1.0F, 1.0F, 1.0F, alpha * 0.55F);
    }

    private static void upright(PoseStack pose, VertexConsumer vc, byte kind, float radius, float yaw,
                                float r, float g, float b, float a) {
        if (a <= 0.004F) {
            return;
        }
        pose.pushPose();
        pose.mulPose(Axis.YP.rotationDegrees(yaw));
        PoseStack.Pose last = pose.last();
        float u0 = kind / (float) SIGIL_CELLS;
        float u1 = (kind + 1) / (float) SIGIL_CELLS;
        vertex(vc, last, -radius, -radius, 0.0F, r, g, b, a, u0, 1.0F);
        vertex(vc, last, -radius, radius, 0.0F, r, g, b, a, u0, 0.0F);
        vertex(vc, last, radius, radius, 0.0F, r, g, b, a, u1, 0.0F);
        vertex(vc, last, radius, -radius, 0.0F, r, g, b, a, u1, 1.0F);
        pose.popPose();
    }

    /** Warning colours per attack kind, so a grasp reads violet and a siphon reads blood. */
    static float[] trackColor(byte kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_GRASP -> new float[] {0.78F, 0.66F, 1.0F};
            case ShowConstants.STRIKE_SIPHON -> new float[] {1.0F, 0.72F, 0.66F};
            case ShowConstants.STRIKE_BARRAGE -> new float[] {1.0F, 0.84F, 0.58F};
            case ShowConstants.STRIKE_LASER -> new float[] {1.0F, 0.94F, 0.74F};
            case ShowConstants.STRIKE_VORTEX -> new float[] {0.85F, 0.12F, 0.48F};
            case ShowConstants.STRIKE_RUPTURE -> new float[] {1.0F, 0.48F, 0.08F};
            default -> new float[] {0.95F, 0.90F, 1.0F};
        };
    }

    static float[] lockColor(byte kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_GRASP -> new float[] {0.82F, 0.22F, 1.0F};
            case ShowConstants.STRIKE_SIPHON -> new float[] {1.0F, 0.06F, 0.04F};
            case ShowConstants.STRIKE_BARRAGE -> new float[] {1.0F, 0.38F, 0.05F};
            case ShowConstants.STRIKE_LASER -> new float[] {1.0F, 0.56F, 0.10F};
            case ShowConstants.STRIKE_VORTEX -> new float[] {0.90F, 0.02F, 0.32F};
            case ShowConstants.STRIKE_RUPTURE -> new float[] {1.0F, 0.28F, 0.02F};
            default -> new float[] {1.0F, 0.10F, 0.07F};
        };
    }

    private static float[] impactColor(byte kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_GRASP -> new float[] {0.80F, 0.45F, 1.0F};
            case ShowConstants.STRIKE_SIPHON -> new float[] {1.0F, 0.28F, 0.22F};
            case ShowConstants.STRIKE_BARRAGE -> new float[] {1.0F, 0.60F, 0.20F};
            case ShowConstants.STRIKE_LASER -> new float[] {1.0F, 0.96F, 0.82F};
            case ShowConstants.STRIKE_VORTEX -> new float[] {1.0F, 0.05F, 0.40F};
            case ShowConstants.STRIKE_RUPTURE -> new float[] {1.0F, 0.55F, 0.08F};
            default -> new float[] {1.0F, 0.86F, 0.68F};
        };
    }

    /** One sigil quad lying in the ground plane. Entities render camera-relative, so the caller has
     * already translated the pose to the mark; only the mark's own spin remains.
     */
    private static void sigil(PoseStack pose, VertexConsumer vc, byte kind, float radius, float spin,
                              float r, float g, float b, float a) {
        if (a <= 0.004F) {
            return;
        }
        pose.pushPose();
        pose.mulPose(Axis.YP.rotationDegrees(spin));
        PoseStack.Pose last = pose.last();
        float u0 = kind / (float) SIGIL_CELLS;
        float u1 = (kind + 1) / (float) SIGIL_CELLS;
        vertex(vc, last, -radius, 0.0F, -radius, r, g, b, a, u0, 1.0F);
        vertex(vc, last, -radius, 0.0F, radius, r, g, b, a, u0, 0.0F);
        vertex(vc, last, radius, 0.0F, radius, r, g, b, a, u1, 0.0F);
        vertex(vc, last, radius, 0.0F, -radius, r, g, b, a, u1, 1.0F);
        pose.popPose();
    }

    private static void vertex(VertexConsumer vc, PoseStack.Pose pose,
                               float x, float y, float z, float r, float g, float b, float a,
                               float u, float v) {
        vc.addVertex(pose, x, y, z)
                .setColor(r, g, b, a)
                .setUv(u, v)
                .setOverlay(OverlayTexture.NO_OVERLAY)
                .setLight(LightTexture.FULL_BRIGHT)
                .setNormal(pose, 0.0F, 1.0F, 0.0F);
    }

    // ------------------------------------------------------------------ beam pass

    /**
     * Every untextured mark of the storm in one pass: the seal rings on the ground, the lance's
     * guide beam, the impact shockwaves and the seal's lightning. All of it rides in the lightning
     * render type (POSITION_COLOR, no texture), so colours are authored per vertex and the pass
     * costs one draw call. The ring and beam helpers emit both windings, because that type culls
     * back faces and a flat ring would otherwise vanish when seen from the other side.
     */
    private static void renderFx(PoseStack pose, MultiBufferSource.BufferSource buffers,
                                 float smooth) {
        List<ShowStrike.Strike> strikes = ShowStrike.strikes();
        List<ShowStrike.Impact> impacts = ShowStrike.impacts();
        if (strikes.isEmpty() && impacts.isEmpty()) {
            return;
        }
        VertexConsumer vc = buffers.getBuffer(RenderType.lightning());
        long now = System.currentTimeMillis();
        for (ShowStrike.Strike strike : strikes) {
            if (strike.laser()) {
                warningBeam(pose, vc, strike, smooth, now);
            } else if (strike.vortex() || strike.rupture()) {
                warningGroundSkill(pose, vc, strike, smooth);
            } else {
                groundGlow(pose, vc, strike, smooth);
            }
        }
        for (ShowStrike.Impact impact : impacts) {
            if (impact.laser()) {
                impactBeam(pose, vc, impact);
            } else if (impact.vortex() || impact.rupture()) {
                impactGroundSkill(pose, vc, impact, smooth);
            } else {
                shockwave(pose, vc, impact, smooth);
            }
        }
        // The discharge draws last so its white core sits over its own bloom.
        for (ShowStrike.Impact impact : impacts) {
            if (impact.bolt() && impact.life() > 0.32F) {
                pose.pushPose();
                pose.translate(impact.x - camX, impact.y - camY, impact.z - camZ);
                bolt(pose, vc, impact, now);
                pose.popPose();
            }
        }
        buffers.endBatch(RenderType.lightning());
    }

    /**
     * The mark on the floor, in three rings: one that closes in as the fuse burns, four arcs
     * sweeping against it, and - once the point is sealed - a white inner ring salted with twelve
     * spikes. It reads as a seal drawing tight, which is what the ground attacks actually do.
     */
    private static void groundGlow(PoseStack pose, VertexConsumer vc, ShowStrike.Strike strike,
                                   float smooth) {
        boolean locked = strike.locked();
        float urgency = strike.urgency();
        float pulse = 0.5F + 0.5F * Mth.sin(smooth * (locked ? 2.2F : 0.9F));
        float[] tint = locked ? lockColor(strike.kind) : trackColor(strike.kind);
        float shrink = 1.55F - 0.55F * urgency;
        pose.pushPose();
        pose.translate(strike.rx() - camX, strike.ry() - camY + 0.05, strike.rz() - camZ);
        Matrix4f m = pose.last().pose();
        float outer = strike.radius * (locked ? 1.18F : shrink);
        ring(m, vc, outer, 0.075F + 0.05F * urgency, tint[0], tint[1], tint[2],
                (locked ? 0.72F : 0.32F) * (0.6F + 0.4F * pulse) * WARN_DIM);
        for (int i = 0; i < 4; i++) {
            arc(m, vc, strike.radius * (1.9F - 0.5F * urgency), 0.10F,
                    smooth * 2.4F + i * 90.0F, 70.0F,
                    tint[0], tint[1], tint[2], (locked ? 0.5F : 0.26F) * pulse * WARN_DIM);
        }
        if (locked) {
            ring(m, vc, strike.radius * 0.72F, 0.05F, 1.0F, 0.94F, 0.84F,
                    (0.28F + 0.34F * pulse) * WARN_DIM);
            for (int i = 0; i < 12; i++) {
                double a = Math.PI * 2.0 * i / 12.0 + smooth * 0.35;
                float x0 = (float) (Math.cos(a) * strike.radius * 1.02);
                float z0 = (float) (Math.sin(a) * strike.radius * 1.02);
                float x1 = (float) (Math.cos(a) * strike.radius * 1.30);
                float z1 = (float) (Math.sin(a) * strike.radius * 1.30);
                beam(m, vc, x0, 0.03F, z0, x1, 0.03F, z1, 0.05F,
                        tint[0], tint[1], tint[2], 0.6F * WARN_DIM);
            }
        } else {
            ring(m, vc, strike.radius * 1.9F * (1.0F - 0.15F * pulse), 0.04F,
                    tint[0], tint[1], tint[2], 0.15F * WARN_DIM);
        }
        pose.popPose();
    }

    /**
     * Where an attack landed: an expanding shockwave ring, eight streaks thrown out along the
     * ground, and - for the bolt - a column of light standing in the crater for as long as the
     * frame lasts.
     */
    private static void shockwave(PoseStack pose, VertexConsumer vc, ShowStrike.Impact impact,
                                  float smooth) {
        float life = impact.life();
        float age = 1.0F - life;
        float[] tint = impactColor(impact.kind);
        pose.pushPose();
        pose.translate(impact.x - camX, impact.y - camY + 0.06, impact.z - camZ);
        Matrix4f m = pose.last().pose();
        ring(m, vc, impact.radius * (1.0F + age * 2.6F), 0.10F * life + 0.03F,
                1.0F, 0.96F, 0.90F, 0.55F * life);
        ring(m, vc, impact.radius * (0.7F + age * 1.1F), 0.30F * life + 0.05F,
                tint[0], tint[1], tint[2], 0.45F * life * life);
        for (int i = 0; i < 8; i++) {
            double a = Math.PI * 2.0 * i / 8.0 + smooth * 0.3;
            float x0 = (float) (Math.cos(a) * impact.radius * 1.1F);
            float z0 = (float) (Math.sin(a) * impact.radius * 1.1F);
            float x1 = (float) (Math.cos(a) * impact.radius * (1.6F + 2.4F * age));
            float z1 = (float) (Math.sin(a) * impact.radius * (1.6F + 2.4F * age));
            beam(m, vc, x0, 0.05F, z0, x1, 0.05F, z1, 0.10F * life,
                    tint[0], tint[1], tint[2], 0.38F * life);
        }
        if (impact.bolt()) {
            pillar(m, vc, life);
        }
        pose.popPose();
    }

    private static void warningGroundSkill(PoseStack pose, VertexConsumer vc,
                                           ShowStrike.Strike strike, float smooth) {
        float urgency = strike.urgency();
        float[] tint = strike.locked() ? lockColor(strike.kind) : trackColor(strike.kind);
        float pulse = 0.75F + 0.25F * Mth.sin(smooth * (strike.locked() ? 1.8F : 0.6F));
        float alpha = (0.35F + urgency * 0.4F) * pulse * WARN_DIM;
        pose.pushPose();
        pose.translate(strike.rx() - camX, strike.ry() - camY + 0.07, strike.rz() - camZ);
        Matrix4f m = pose.last().pose();
        ring(m, vc, strike.radius, 0.08F + urgency * 0.06F,
                tint[0], tint[1], tint[2], alpha);
        if (strike.vortex()) {
            inwardSpiral(m, vc, strike.radius, smooth, 1.0F, tint, alpha);
        } else {
            spikeCrown(m, vc, strike.radius, 0.2F + urgency * 0.65F,
                    smooth, tint, alpha);
        }
        pose.popPose();
    }

    private static void impactGroundSkill(PoseStack pose, VertexConsumer vc,
                                          ShowStrike.Impact impact, float smooth) {
        float life = impact.life();
        float age = 1.0F - life;
        float[] tint = impactColor(impact.kind);
        pose.pushPose();
        pose.translate(impact.x - camX, impact.y - camY + 0.08, impact.z - camZ);
        Matrix4f m = pose.last().pose();
        if (impact.vortex()) {
            float radius = impact.radius * (0.08F + 0.92F * life);
            ring(m, vc, radius, 0.12F + life * 0.18F, tint[0], tint[1], tint[2], life);
            inwardSpiral(m, vc, radius, smooth * 2.0F, life, tint, life * 0.85F);
            beam(m, vc, 0.0F, 0.03F, 0.0F, 0.0F, 0.7F * life, 0.0F,
                    0.35F * life, 1.0F, 0.28F, 0.55F, life * life);
        } else {
            float rise = Mth.clamp(age / 0.22F, 0.0F, 1.0F);
            spikeCrown(m, vc, impact.radius, (0.4F + 4.8F * rise) * (0.65F + 0.35F * life),
                    smooth, tint, life * 0.85F);
            ring(m, vc, impact.radius * (1.0F + age * 0.3F), 0.18F * life,
                    tint[0], tint[1], tint[2], life * 0.65F);
        }
        pose.popPose();
    }

    private static void inwardSpiral(Matrix4f m, VertexConsumer vc, float radius,
                                     float smooth, float lift, float[] tint, float alpha) {
        for (int arm = 0; arm < 3; arm++) {
            double base = arm * Math.PI * 2.0 / 3.0 - smooth * 0.055;
            for (int i = 0; i < 32; i++) {
                float t0 = i / 32.0F;
                float t1 = (i + 1) / 32.0F;
                double a0 = base + t0 * Math.PI * 1.5;
                double a1 = base + t1 * Math.PI * 1.5;
                float r0 = radius * (1.0F - 0.92F * t0);
                float r1 = radius * (1.0F - 0.92F * t1);
                float width = 0.045F + 0.045F * (1.0F - t0);
                band(m, vc, (float) Math.cos(a0) * r0, (float) Math.sin(a0) * r0,
                        (float) Math.cos(a0) * (r0 - width), (float) Math.sin(a0) * (r0 - width),
                        (float) Math.cos(a1) * (r1 - width), (float) Math.sin(a1) * (r1 - width),
                        (float) Math.cos(a1) * r1, (float) Math.sin(a1) * r1,
                        tint[0], tint[1], tint[2], alpha * (0.45F + t0 * 0.55F));
            }
            for (int mote = 0; mote < 3; mote++) {
                float travel = smooth * 0.025F + mote / 3.0F;
                float t = travel - (float) Math.floor(travel);
                double angle = base + t * Math.PI * 1.5;
                float r = radius * (1.0F - 0.92F * t);
                float x = (float) Math.cos(angle) * r;
                float z = (float) Math.sin(angle) * r;
                beam(m, vc, x, 0.08F + (1.0F - t) * 0.35F * lift, z,
                        x * 0.86F, 0.06F, z * 0.86F, 0.055F,
                        1.0F, 0.25F, 0.58F, alpha);
            }
        }
    }

    private static void spikeCrown(Matrix4f m, VertexConsumer vc, float radius,
                                   float height, float smooth, float[] tint, float alpha) {
        for (int i = 0; i < 12; i++) {
            double angle = Math.PI * 2.0 * i / 12.0;
            float cx = (float) Math.cos(angle);
            float cz = (float) Math.sin(angle);
            float r = radius * (i % 2 == 0 ? 0.72F : 0.92F);
            float x = cx * r;
            float z = cz * r;
            float h = height * (0.68F + (i % 3) * 0.16F)
                    * (0.95F + 0.05F * Mth.sin(smooth * 0.9F + i));
            float width = 0.22F;
            float ax = x - cz * width;
            float az = z + cx * width;
            float bx = x + cz * width;
            float bz = z - cx * width;
            float tx = x + cx * 0.25F - cz * 0.16F;
            float tz = z + cz * 0.25F + cx * 0.16F;
            float kx = x - cx * 0.12F + cz * 0.22F;
            float kz = z - cz * 0.12F - cx * 0.22F;
            quad(m, vc, ax, 0.0F, az, bx, 0.0F, bz, tx, h, tz, kx, h * 0.48F, kz,
                    tint[0], tint[1], tint[2], alpha * 0.48F);
            quad(m, vc, kx, h * 0.48F, kz, tx, h, tz, bx, 0.0F, bz, ax, 0.0F, az,
                    tint[0], tint[1], tint[2], alpha * 0.48F);
            beam(m, vc, x, 0.02F, z, kx, h * 0.48F, kz, 0.075F,
                    tint[0], tint[1], tint[2], alpha);
            beam(m, vc, kx, h * 0.48F, kz, tx, h, tz, 0.035F,
                    1.0F, 0.78F, 0.34F, alpha);
            beam(m, vc, cx * radius * 0.2F, 0.02F, cz * radius * 0.2F,
                    x - cz * 0.25F, 0.02F, z + cx * 0.25F, 0.045F,
                    tint[0], tint[1], tint[2], alpha * 0.6F);
            beam(m, vc, x - cz * 0.25F, 0.02F, z + cx * 0.25F, x, 0.02F, z,
                    0.045F, tint[0], tint[1], tint[2], alpha * 0.6F);
        }
    }

    /** The bolt's crater light: a tapered hot column standing where the discharge landed. */
    private static void pillar(Matrix4f m, VertexConsumer vc, float life) {
        float sway = Mth.sin(life * 26.0F) * 0.05F;
        beam(m, vc, 0.0F, 0.02F, 0.0F, sway, 9.5F, -sway, 0.85F,
                0.95F, 0.10F, 0.05F, 0.18F * life);
        beam(m, vc, 0.0F, 0.02F, 0.0F, sway, 5.5F, -sway, 0.34F,
                1.0F, 0.52F, 0.24F, 0.28F * life);
        beam(m, vc, 0.0F, 0.02F, 0.0F, sway, 3.0F, -sway, 0.13F,
                1.0F, 0.96F, 0.88F, 0.42F * life);
    }

    /** Angle of the sky anchor around the mark; stable for a given x/z on every client. */
    private static double beamAngle(double x, double z) {
        double h = Math.sin(x * 12.9898 + z * 78.233) * 43758.5453;
        return (h - Math.floor(h)) * Math.PI * 2.0;
    }

    private static void warningBeam(PoseStack pose, VertexConsumer vc, ShowStrike.Strike strike,
                                    float smooth, long now) {
        boolean locked = strike.locked();
        float urgency = strike.urgency();
        float[] tint = locked ? lockColor(strike.kind) : trackColor(strike.kind);
        double angle = beamAngle(strike.rx(), strike.rz());
        float ox = (float) (Math.cos(angle) * BEAM_DISTANCE);
        float oy = (float) BEAM_HEIGHT;
        float oz = (float) (Math.sin(angle) * BEAM_DISTANCE);
        // A charge pulse runs down the line as the fuse burns, and the guide thickens to a column
        // once the lock seals the point.
        float pulse = 0.5F + 0.5F * Mth.sin(smooth * (locked ? 9.0F : 4.5F));
        float width = (locked ? 0.26F : 0.06F + 0.17F * urgency) * (0.8F + 0.2F * pulse);
        float alpha = (locked ? 0.50F : 0.16F + 0.30F * urgency) * (0.7F + 0.3F * pulse) * WARN_DIM;
        RandomSource rnd = RandomSource.create((long) (strike.rx() * 64.0)
                ^ (long) (strike.rz() * 64.0) ^ (now / 90L));
        float jx = (rnd.nextFloat() - 0.5F) * 2.2F;
        float jz = (rnd.nextFloat() - 0.5F) * 2.2F;

        pose.pushPose();
        pose.translate(strike.rx() - camX, strike.ry() - camY, strike.rz() - camZ);
        Matrix4f m = pose.last().pose();
        beam(m, vc, ox, oy, oz, ox * 0.5F + jx, oy * 0.5F, oz * 0.5F + jz,
                width * 2.2F, tint[0], tint[1], tint[2], alpha * 0.45F);
        beam(m, vc, ox, oy, oz, ox * 0.5F + jx, oy * 0.5F, oz * 0.5F + jz,
                width, tint[0], tint[1], tint[2], alpha);
        beam(m, vc, ox * 0.5F + jx, oy * 0.5F, oz * 0.5F + jz, 0.0F, 0.0F, 0.0F,
                width * 2.2F, tint[0], tint[1], tint[2], alpha * 0.45F);
        beam(m, vc, ox * 0.5F + jx, oy * 0.5F, oz * 0.5F + jz, 0.0F, 0.0F, 0.0F,
                width, tint[0], tint[1], tint[2], alpha);
        beam(m, vc, ox, oy, oz, 0.0F, 0.0F, 0.0F, width * 0.35F, 1.0F, 0.97F, 0.88F,
                alpha * (locked ? 0.85F : 0.5F));
        pose.popPose();
    }

    private static void impactBeam(PoseStack pose, VertexConsumer vc, ShowStrike.Impact impact) {
        float life = impact.life();
        double angle = beamAngle(impact.x, impact.z);
        float ox = (float) (Math.cos(angle) * BEAM_DISTANCE);
        float oy = (float) BEAM_HEIGHT;
        float oz = (float) (Math.sin(angle) * BEAM_DISTANCE);
        float grow = 0.55F + 0.45F * life;
        pose.pushPose();
        pose.translate(impact.x - camX, impact.y - camY, impact.z - camZ);
        Matrix4f m = pose.last().pose();
        beam(m, vc, ox, oy, oz, 0.0F, 0.0F, 0.0F, 0.62F * grow, 1.0F, 0.40F, 0.08F, 0.45F * life);
        beam(m, vc, ox, oy, oz, 0.0F, 0.0F, 0.0F, 0.30F * grow, 1.0F, 0.74F, 0.34F, 0.65F * life);
        beam(m, vc, ox, oy, oz, 0.0F, 0.0F, 0.0F, 0.11F * grow, 1.0F, 1.0F, 0.95F, 0.95F * life);
        pose.popPose();
    }

    /** A ribbon along an arbitrary line, drawn in two perpendicular planes. */
    private static void beam(Matrix4f m, VertexConsumer vc,
                             float x1, float y1, float z1, float x2, float y2, float z2,
                             float w, float r, float g, float b, float a) {
        if (a <= 0.004F) {
            return;
        }
        float dx = x2 - x1;
        float dy = y2 - y1;
        float dz = z2 - z1;
        float len = Mth.sqrt(dx * dx + dy * dy + dz * dz);
        if (len < 1.0E-4F) {
            return;
        }
        dx /= len;
        dy /= len;
        dz /= len;
        float sx;
        float sy = 0.0F;
        float sz;
        if (Math.abs(dy) > 0.99F) {
            sx = 1.0F;
            sz = 0.0F;
        } else {
            sx = -dz;
            sz = dx;
            float l = Mth.sqrt(sx * sx + sz * sz);
            sx /= l;
            sz /= l;
        }
        float ux = sy * dz - sz * dy;
        float uy = sz * dx - sx * dz;
        float uz = sx * dy - sy * dx;
        quad(m, vc, x1 - sx * w, y1 - sy * w, z1 - sz * w,
                x1 + sx * w, y1 + sy * w, z1 + sz * w,
                x2 + sx * w, y2 + sy * w, z2 + sz * w,
                x2 - sx * w, y2 - sy * w, z2 - sz * w, r, g, b, a);
        quad(m, vc, x2 - sx * w, y2 - sy * w, z2 - sz * w,
                x2 + sx * w, y2 + sy * w, z2 + sz * w,
                x1 + sx * w, y1 + sy * w, z1 + sz * w,
                x1 - sx * w, y1 - sy * w, z1 - sz * w, r, g, b, a);
        quad(m, vc, x1 - ux * w, y1 - uy * w, z1 - uz * w,
                x1 + ux * w, y1 + uy * w, z1 + uz * w,
                x2 + ux * w, y2 + uy * w, z2 + uz * w,
                x2 - ux * w, y2 - uy * w, z2 - uz * w, r, g, b, a);
        quad(m, vc, x2 - ux * w, y2 - uy * w, z2 - uz * w,
                x2 + ux * w, y2 + uy * w, z2 + uz * w,
                x1 + ux * w, y1 + uy * w, z1 + uz * w,
                x1 - ux * w, y1 - uy * w, z1 - uz * w, r, g, b, a);
    }

    // ------------------------------------------------------------------ bolt pass

    /**
     * The seal's lightning, drawn by us instead of vanilla: a jagged crimson discharge that tapers
     * as it climbs, with a halo, a red body, an orange inner and a white-hot core, three forks and
     * a fresh seed every few frames so it shivers instead of standing still. It comes from the same
     * impact payload as the ground bloom, so every client sees the bolt on the exact mark the
     * server struck, and the boss's immunity stays a server-side rule.
     */
    private static void bolt(PoseStack pose, VertexConsumer vc, ShowStrike.Impact impact, long now) {
        float alive = Mth.clamp((impact.life() - 0.2F) / 0.8F, 0.0F, 1.0F);
        Matrix4f m = pose.last().pose();
        // Re-seeding on a short clock makes the trunk shiver instead of standing still.
        long seed = (long) (impact.x * 4096.0) * 31L ^ (long) (impact.z * 4096.0)
                ^ impact.startMs ^ (now / 60L);
        RandomSource rnd = RandomSource.create(seed);
        float height = 76.0F;
        int segments = 16;
        float[] ox = new float[segments + 1];
        float[] oz = new float[segments + 1];
        float dx = 0.0F;
        float dz = 0.0F;
        for (int i = segments; i >= 0; i--) {
            ox[i] = dx;
            oz[i] = dz;
            dx += (rnd.nextFloat() - 0.5F) * 3.0F;
            dz += (rnd.nextFloat() - 0.5F) * 3.0F;
        }
        float flicker = 0.74F + 0.26F * Mth.sin(now * 0.045F);
        for (int i = 0; i < segments; i++) {
            float y0 = height * (1.0F - i / (float) segments);
            float y1 = height * (1.0F - (i + 1) / (float) segments);
            // Thinner toward the sky: the bolt is fattest where it dumps its charge.
            float taper = 1.0F - 0.45F * i / (float) segments;
            segment(m, vc, ox[i], y0, oz[i], ox[i + 1], y1, oz[i + 1],
                    1.05F * taper, 0.95F, 0.06F, 0.03F, 0.16F * alive * flicker);
            segment(m, vc, ox[i], y0, oz[i], ox[i + 1], y1, oz[i + 1],
                    0.52F * taper, 1.0F, 0.10F, 0.07F, 0.38F * alive * flicker);
            segment(m, vc, ox[i], y0, oz[i], ox[i + 1], y1, oz[i + 1],
                    0.24F * taper, 1.0F, 0.42F, 0.16F, 0.5F * alive);
            segment(m, vc, ox[i], y0, oz[i], ox[i + 1], y1, oz[i + 1],
                    0.10F * taper, 1.0F, 0.88F, 0.80F, 0.94F * alive);
        }
        // Three forks peel off the trunk so it reads as one discharge, not a stripe.
        fork(m, vc, rnd, ox, oz, height, segments, 3, 1.0F, alive);
        fork(m, vc, rnd, ox, oz, height, segments, 7, -1.0F, alive * 0.85F);
        fork(m, vc, rnd, ox, oz, height, segments, 12, 1.0F, alive * 0.6F);
    }

    private static void fork(Matrix4f m, VertexConsumer vc, RandomSource rnd,
                             float[] ox, float[] oz, float height, int segments,
                             int at, float side, float alive) {
        float x = ox[at];
        float z = oz[at];
        float y = height * (1.0F - at / (float) segments);
        float len = height * 0.05F;
        for (int i = 0; i < 3; i++) {
            float nx = x + (rnd.nextFloat() * 1.6F + 1.2F) * side;
            float nz = z + (rnd.nextFloat() - 0.5F) * 2.6F;
            float ny = y - len;
            segment(m, vc, x, y, z, nx, ny, nz, 0.34F, 0.95F, 0.10F, 0.05F, 0.20F * alive);
            segment(m, vc, x, y, z, nx, ny, nz, 0.12F, 1.0F, 0.62F, 0.55F, 0.55F * alive);
            x = nx;
            z = nz;
            y = ny;
        }
    }

    /** One ribbon segment, drawn in two perpendicular planes so it reads from any angle. */
    private static void segment(Matrix4f m, VertexConsumer vc, float x1, float y1, float z1,
                                float x2, float y2, float z2, float w,
                                float r, float g, float b, float a) {
        if (a <= 0.004F) {
            return;
        }
        quad(m, vc, x1 - w, y1, z1, x2 - w, y2, z2, x2 + w, y2, z2, x1 + w, y1, z1, r, g, b, a);
        quad(m, vc, x1, y1, z1 - w, x2, y2, z2 - w, x2, y2, z2 + w, x1, y1, z1 + w, r, g, b, a);
    }

    /** A flat ring in the mark's own plane, filled inward from {@code radius}. */
    private static void ring(Matrix4f m, VertexConsumer vc, float radius, float thickness,
                             float r, float g, float b, float a) {
        if (a <= 0.004F || radius <= 0.02F) {
            return;
        }
        int n = 48;
        float inner = Math.max(0.0F, radius - Math.max(0.02F, thickness));
        for (int i = 0; i < n; i++) {
            double a0 = Math.PI * 2.0 * i / n;
            double a1 = Math.PI * 2.0 * (i + 1) / n;
            float c0 = (float) Math.cos(a0);
            float s0 = (float) Math.sin(a0);
            float c1 = (float) Math.cos(a1);
            float s1 = (float) Math.sin(a1);
            band(m, vc, c0 * inner, s0 * inner, c0 * radius, s0 * radius,
                    c1 * radius, s1 * radius, c1 * inner, s1 * inner, r, g, b, a);
        }
    }

    /** An arc of a ring, {@code span} degrees wide, spun to {@code startDeg}. */
    private static void arc(Matrix4f m, VertexConsumer vc, float radius, float thickness,
                            float startDeg, float span,
                            float r, float g, float b, float a) {
        if (a <= 0.004F) {
            return;
        }
        float inner = Math.max(0.0F, radius - Math.max(0.02F, thickness));
        int n = 10;
        for (int i = 0; i < n; i++) {
            double a0 = Math.toRadians(startDeg + span * i / n);
            double a1 = Math.toRadians(startDeg + span * (i + 1) / n);
            float c0 = (float) Math.cos(a0);
            float s0 = (float) Math.sin(a0);
            float c1 = (float) Math.cos(a1);
            float s1 = (float) Math.sin(a1);
            band(m, vc, c0 * inner, s0 * inner, c0 * radius, s0 * radius,
                    c1 * radius, s1 * radius, c1 * inner, s1 * inner, r, g, b, a);
        }
    }

    /** One quad of the ground plane, emitted with both windings so either face shows. */
    private static void band(Matrix4f m, VertexConsumer vc,
                             float ax, float az, float bx, float bz,
                             float cx, float cz, float dx, float dz,
                             float r, float g, float b, float a) {
        quad(m, vc, ax, 0.0F, az, bx, 0.0F, bz, cx, 0.0F, cz, dx, 0.0F, dz, r, g, b, a);
        quad(m, vc, dx, 0.0F, dz, cx, 0.0F, cz, bx, 0.0F, bz, ax, 0.0F, az, r, g, b, a);
    }

    private static void quad(Matrix4f m, VertexConsumer vc,
                             float ax, float ay, float az, float bx, float by, float bz,
                             float cx, float cy, float cz, float dx, float dy, float dz,
                             float r, float g, float b, float a) {
        vc.addVertex(m, ax, ay, az).setColor(r, g, b, a);
        vc.addVertex(m, bx, by, bz).setColor(r, g, b, a);
        vc.addVertex(m, cx, cy, cz).setColor(r, g, b, a);
        vc.addVertex(m, dx, dy, dz).setColor(r, g, b, a);
    }

    // ------------------------------------------------------------------ HUD pass

    public static void renderHud(GuiGraphics g) {
        if (!ShowStrike.active() || !haveMatrices) {
            return;
        }
        int w = g.guiWidth();
        int h = g.guiHeight();
        var font = Minecraft.getInstance().font;
        long now = System.currentTimeMillis();

        for (ShowStrike.Strike strike : ShowStrike.strikes()) {
            marker(g, font, strike, w, h);
        }

        // Local reactions: a soft red edge while a mark covers you, a brief flash when it lands.
        // Kept low on purpose - the player's glow and the reticle carry the warning now, so the
        // screen never has to shout to be noticed.
        float edge = 0.0F;
        if (ShowStrike.endangered()) {
            float pulse = 0.5F + 0.5F * Mth.sin((float) (now % 520L) / 520.0F * 2.0F * (float) Math.PI);
            edge = 0.16F + 0.12F * pulse;
        }
        long hitAge = ShowStrike.hitAge();
        if (hitAge < ShowStrike.hitWindow()) {
            edge = Math.max(edge, 0.45F * (1.0F - hitAge / (float) ShowStrike.hitWindow()));
        }
        if (edge > 0.0F) {
            vignette(g, w, h, edge);
        }
        if (hitAge < ShowStrike.hitWindow() * 0.6F) {
            int a = Math.round(70 * (1.0F - hitAge / (ShowStrike.hitWindow() * 0.6F)));
            g.fill(0, 0, w, h, (a << 24) | 0xE01408);
        }
        long dodgeAge = ShowStrike.dodgeAge();
        if (dodgeAge < ShowStrike.dodgeWindow()) {
            float fade = 1.0F - dodgeAge / (float) ShowStrike.dodgeWindow();
            int color = ((int) (255 * fade) << 24) | 0x9BE8FF;
            g.pose().pushPose();
            g.pose().translate(w / 2.0F, h / 2.0F + 46.0F, 0.0F);
            g.pose().scale(1.5F, 1.5F, 1.0F);
            g.drawCenteredString(font, "DODGED", 0, 0, color);
            g.pose().popPose();
        }
        banner(g, font, w, now);
    }

    /** The mark on screen: the sigil, four closing brackets and a fuse that burns down. */
    private static void marker(GuiGraphics g, net.minecraft.client.gui.Font font,
                               ShowStrike.Strike strike, int w, int h) {
        boolean locked = strike.locked();
        if (project(strike.rx(), strike.ry(), strike.rz())) {
            boolean onScreen = Math.abs(NDC[0]) <= 1.0F && Math.abs(NDC[1]) <= 1.0F;
            float sx = (NDC[0] * 0.5F + 0.5F) * w;
            float sy = (0.5F - NDC[1] * 0.5F) * h;
            if (!onScreen) {
                float len = Math.max(Math.abs(NDC[0]), Math.abs(NDC[1]));
                float nx = NDC[0] / len;
                float ny = NDC[1] / len;
                int ex = Mth.clamp(Math.round((nx * 0.5F + 0.5F) * w), EDGE, w - EDGE);
                int ey = Mth.clamp(Math.round((0.5F - ny * 0.5F) * h), EDGE, h - EDGE);
                edgeMark(g, font, strike, ex, ey, nx, -ny);
            } else {
                reticle(g, font, strike, Math.round(sx), Math.round(sy), locked);
            }
        } else {
            // Behind the camera: park an arrow on the side it lies, low enough to never cover the bar.
            double dx = strike.rx() - camX;
            double dz = strike.rz() - camZ;
            int ex = dx >= 0.0 ? w - EDGE : EDGE;
            int ey = h * 3 / 5;
            edgeMark(g, font, strike, ex, ey, dx >= 0.0 ? 1.0F : -1.0F, 0.0F);
        }
    }

    private static void reticle(GuiGraphics g, net.minecraft.client.gui.Font font,
                                ShowStrike.Strike strike, int x, int y, boolean locked) {
        float urgency = strike.urgency();
        int size = 22 + Math.round(8.0F * urgency);
        float pulse = 0.5F + 0.5F * Mth.sin(urgency * 40.0F);
        float alpha = locked ? 0.6F : 0.4F + 0.2F * pulse;
        float[] tint = locked ? lockColor(strike.kind) : trackColor(strike.kind);
        tint(g, tint[0], tint[1], tint[2], alpha);
        g.blit(SIGIL, x - size / 2, y - size / 2, size, size,
                strike.kind * SIGIL_TEX, 0, SIGIL_TEX, SIGIL_TEX, SIGIL_TEX * SIGIL_CELLS, SIGIL_TEX);
        g.setColor(1.0F, 1.0F, 1.0F, 1.0F);

        int color = locked ? colorOf(tint) : 0xEDE7FF;
        int arm = locked ? 9 : 6;
        int gap = size / 2 + 4;
        // Four brackets that close in as the fuse burns down.
        for (int i = -1; i <= 1; i += 2) {
            for (int j = -1; j <= 1; j += 2) {
                int bx = x + i * gap;
                int by = y + j * gap;
                g.fill(bx, by, bx + (i > 0 ? -arm : arm), by + 1, color);
                g.fill(bx, by, bx + 1, by + (j > 0 ? -arm : arm), color);
            }
        }

        // Countdown pips: one dot per second left, the newest one burning white, so the time
        // reads at a glance without squinting at the fuse bar.
        int seconds = Math.max(0, Math.round(strike.ticksLeft / 20.0F));
        int pipSpan = (seconds - 1) * 6;
        for (int i = 0; i < seconds; i++) {
            int px = x - pipSpan / 2 + i * 6;
            int py = y - gap - 6;
            int pc = i == seconds - 1 ? 0xFFFFF3E0 : color;
            g.fill(px - 1, py - 1, px + 1, py + 1, pc);
        }

        // The fuse: one bar per warning second, shrinking toward the attack.
        int fw = 46;
        int fx = x - fw / 2;
        int fy = y + gap + 7;
        g.fill(fx, fy, fx + fw, fy + 3, 0x60000000);
        g.fill(fx, fy, fx + Math.round(fw * urgency), fy + 3, locked ? 0xFFE0C0 : 0xD9FFFFFF);
        String label = locked ? callout(strike) : Math.round(strike.ticksLeft / 20.0F) + "s";
        int lw = font.width(label);
        int ly = fy + 6;
        g.drawString(font, label, x - lw / 2 + 1, ly + 1, 0x60000000, false);
        g.drawString(font, label, x - lw / 2, ly, color, false);
    }

    /** The lock call names what is about to land, so the player knows what to run from. */
    private static String callout(ShowStrike.Strike strike) {
        if (strike.grasp()) {
            return "ROOT!";
        }
        if (strike.siphon()) {
            return "DRAIN!";
        }
        if (strike.barrage()) {
            return "SCATTER!";
        }
        if (strike.laser()) {
            return "BREAK LINE!";
        }
        if (strike.vortex()) {
            return "ESCAPE PULL!";
        }
        if (strike.rupture()) {
            return "MOVE!";
        }
        return "DODGE!";
    }

    private static int colorOf(float[] c) {
        return (255 << 24) | (Math.round(c[0] * 255) << 16)
                | (Math.round(c[1] * 255) << 8) | Math.round(c[2] * 255);
    }

    private static void edgeMark(GuiGraphics g, net.minecraft.client.gui.Font font,
                                 ShowStrike.Strike strike, int x, int y, float dx, float dy) {
        int size = 18;
        float[] tint = strike.locked() ? lockColor(strike.kind) : trackColor(strike.kind);
        int color = colorOf(tint);
        tint(g, tint[0], tint[1], tint[2], 0.55F);
        g.blit(SIGIL, x - size / 2, y - size / 2, size, size,
                strike.kind * SIGIL_TEX, 0, SIGIL_TEX, SIGIL_TEX, SIGIL_TEX * SIGIL_CELLS, SIGIL_TEX);
        g.setColor(1.0F, 1.0F, 1.0F, 1.0F);
        // A short pointer toward the edge the mark lies past.
        int tx = x + Math.round(dx * 18.0F);
        int ty = y + Math.round(dy * 18.0F);
        line(g, x + Math.round(dx * 12.0F), y + Math.round(dy * 12.0F), tx, ty, color);
        String label = Math.round(strike.ticksLeft / 20.0F) + "s";
        g.drawString(font, label, x - font.width(label) / 2 + 1, y + size / 2 + 1, color, false);
    }

    /** The wave call: a short banner that names the storm and whether it is aimed here. */
    private static void banner(GuiGraphics g, net.minecraft.client.gui.Font font, int w, long now) {
        long age = ShowStrike.waveAge();
        if (age >= ShowStrike.waveWindow()) {
            return;
        }
        float fade = 1.0F - age / (float) ShowStrike.waveWindow();
        float in = Mth.clamp(age / 180.0F, 0.0F, 1.0F);
        int alpha = Math.round(255.0F * fade * in);
        boolean spared = ShowStrike.spared();
        String attacks = attackName(ShowStrike.waveKind());
        if (ShowStrike.waveFollowupKind() >= 0) {
            attacks += " > " + attackName(ShowStrike.waveFollowupKind());
        }
        String head;
        String sub;
        int headColor;
        if (spared) {
            head = "THE STORM SPARES YOU";
            sub = attacks + "  -  YOU ARE SPARED";
            headColor = (alpha << 24) | 0xFFD98A;
        } else {
            head = "RONOVA CALLS THE STORM";
            sub = "WAVE " + ShowStrike.wave() + "  -  " + attacks + "  -  "
                    + ShowStrike.waveTargets() + " MARKED";
            headColor = (alpha << 24) | 0xE8E0FF;
        }
        int subColor = (Math.round(alpha * 0.8F) << 24) | (spared ? 0xE8C06A : 0xD04A3A);
        int hw = font.width(head);
        int sw = font.width(sub);
        int pad = 10;
        int width = Math.max(hw, sw) + pad * 2;
        float scale = Math.min(1.0F, Math.max(1, w - 16) / (float) width);
        g.pose().pushPose();
        g.pose().translate(w / 2.0F, 38.0F, 0.0F);
        g.pose().scale(scale, scale, 1.0F);
        g.fill(-width / 2, -5, (width + 1) / 2, 25, (Math.round(alpha * 0.30F) << 24));
        // An accent rule in the incoming attack's colour, and a glint that sweeps the panel:
        // the call reads as a living seal instead of a static label.
        float[] accent = lockColor((byte) ShowStrike.waveKind());
        int accentColor = (Math.round(alpha * 0.85F) << 24)
                | (Math.round(accent[0] * 255) << 16) | (Math.round(accent[1] * 255) << 8)
                | Math.round(accent[2] * 255);
        g.fill(-sw / 2, 22, sw / 2, 23, accentColor);
        float sweep = (now % 1800L) / 1800.0F;
        float gx = -width / 2.0F + sweep * (width + 60.0F) - 30.0F;
        for (int i = -12; i <= 12; i++) {
            int px = Math.round(gx) + i;
            if (px < -width / 2 || px >= (width + 1) / 2) {
                continue;
            }
            float fall = 1.0F - Math.abs(i) / 13.0F;
            int ga = Math.round(alpha * 0.16F * fall * fall);
            if (ga > 0) {
                g.fill(px, -5, px + 1, 25, (ga << 24) | 0xFFF3E0);
            }
        }
        g.drawString(font, head, -hw / 2 + 1, 1, (Math.round(alpha * 0.5F) << 24), false);
        g.drawString(font, head, -hw / 2, 0, headColor, false);
        g.drawString(font, sub, -sw / 2, 12, subColor, false);
        g.pose().popPose();
    }

    private static String attackName(int kind) {
        return switch (kind) {
            case ShowConstants.STRIKE_BOLT -> "RED BOLT";
            case ShowConstants.STRIKE_GRASP -> "BINDING SIGN";
            case ShowConstants.STRIKE_SIPHON -> "SOUL SIPHON";
            case ShowConstants.STRIKE_BARRAGE -> "EMBER BARRAGE";
            case ShowConstants.STRIKE_LASER -> "SEAL LANCE";
            case ShowConstants.STRIKE_VORTEX -> "CRIMSON VORTEX";
            case ShowConstants.STRIKE_RUPTURE -> "RIFT ERUPTION";
            default -> "STORM";
        };
    }

    /** Red edges that thicken toward the border, so the danger reads without covering the view. */
    private static void vignette(GuiGraphics g, int w, int h, float strength) {
        int depth = Math.round(h * 0.12F);
        for (int i = 0; i < depth; i++) {
            float t = 1.0F - i / (float) depth;
            int a = Math.round(70.0F * strength * t * t * t);
            int color = (a << 24) | 0xC81608;
            g.fill(i, i, w - i, i + 1, color);
            g.fill(i, h - i - 1, w - i, h - i, color);
            g.fill(i, i, i + 1, h - i, color);
            g.fill(w - i - 1, i, w - i, h - i, color);
        }
    }

    private static void tint(GuiGraphics g, float r, float gg, float b, float a) {
        g.setColor(r, gg, b, a);
    }

    private static void line(GuiGraphics g, int x1, int y1, int x2, int y2, int color) {
        int steps = Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1));
        if (steps == 0) {
            g.fill(x1, y1, x1 + 1, y1 + 1, color);
            return;
        }
        for (int i = 0; i <= steps; i++) {
            int x = x1 + Math.round((x2 - x1) * i / (float) steps);
            int y = y1 + Math.round((y2 - y1) * i / (float) steps);
            g.fill(x, y, x + 1, y + 1, color);
        }
    }

    /**
     * Projects a world point to NDC through the level's own matrices. False when the point is
     * behind the camera, where a projection would land on the wrong side of the screen.
     */
    private static boolean project(double wx, double wy, double wz) {
        POINT.set((float) (wx - camX), (float) (wy - camY), (float) (wz - camZ), 1.0F);
        POINT.mul(VIEW);
        if (POINT.z > -0.05F) {
            return false;
        }
        POINT.mul(PROJ);
        if (POINT.w <= 0.0001F) {
            return false;
        }
        NDC[0] = POINT.x / POINT.w;
        NDC[1] = POINT.y / POINT.w;
        return true;
    }
}
