package net.deusexmachina.client;

import com.mojang.blaze3d.systems.RenderSystem;

import net.deusexmachina.ShowConstants;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.api.distmarker.OnlyIn;

/**
 * Draws the show onto two Gui layers. The HUD layer (above the actionbar) lays the disc, box, timer
 * and lyric out with the same pen advances the datapack's font providers produced, so the bar lands
 * pixel-for-pixel where the old actionbar did. The wash layer (above the title) paints the red veil,
 * the intro heart and the burst - veil first, sprite over it, which is the order the shipped title
 * strings used so the red sky shows through the transparent parts of the blast.
 *
 * <p>Every geometry number here was measured out of the shipped atlases and font JSONs by
 * deus/make_client_data.py and cross-checked against the hudview/skyview simulators: glyph top is
 * {@code 7 - ascent}, the title pose is scale 4 at y=-10, and the actionbar pen starts at
 * {@code (guiWidth - width) / 2} on the line {@code guiHeight - 72}.
 */
@OnlyIn(Dist.CLIENT)
public final class ShowRender {
    private static final ResourceLocation HEART = tex("heart_pulse");
    private static final ResourceLocation BURST = tex("heart_burst");
    private static final ResourceLocation LYRIC = tex("lyric");
    private static final ResourceLocation BOX = tex("box");
    private static final ResourceLocation DIGITS = tex("digits");
    private static final ResourceLocation DISC_C = tex("disc_c");
    private static final ResourceLocation[] DISC_V = {
        tex("disc_v0"), tex("disc_v1"), tex("disc_v2"), tex("disc_v3"), tex("disc_v4")
    };

    private static final int WASH_R = 190;
    private static final int WASH_G = 8;
    private static final int WASH_B = 16;
    private static final int RED = 0xFF5555;
    /** One font pixel of title shadow, which the 4x title pose turns into four GUI pixels. */
    private static final int SHADOW_OFFSET = 4;
    /** Widest and tallest the beat ring reaches in the 256 px heart cell, faint halo included. */
    private static final int RING_W = 230;
    private static final int RING_H = 194;

    private static final ResourceLocation BOSS_FRAME = tex("boss_frame");
    private static final ResourceLocation BOSS_FILL = tex("boss_fill");
    private static final ResourceLocation BOSS_NAME = tex("boss_name");
    /** The frame's own alpha, blurred: blitted behind the bar it blooms along the gothic silhouette. */
    private static final ResourceLocation BOSS_GLOW = tex("boss_frame_glow");
    /** Keyed frame art and the hollow interior the fill is clipped to, both in texture pixels. */
    private static final int BOSS_TEX_W = 1024;
    private static final int BOSS_TEX_H = 255;
    private static final int BOSS_GLOW_W = 1056;
    private static final int BOSS_GLOW_H = 287;
    private static final int BOSS_GLOW_PAD = 16;
    private static final int BOSS_FILL_X0 = 93;
    private static final int BOSS_FILL_X1 = 931;
    private static final int BOSS_FILL_Y0 = 99;
    private static final int BOSS_FILL_Y1 = 159;

    private ShowRender() {
    }

    private static ResourceLocation tex(String name) {
        return ResourceLocation.fromNamespaceAndPath("deusexmachina", "textures/show/" + name + ".png");
    }

    private static int barY(GuiGraphics g) {
        return g.guiHeight() - 72;
    }

    // ------------------------------------------------------------------ wash layer

    public static void renderWash(GuiGraphics g, DeltaTracker delta) {
        if (!ShowTimeline.active()) {
            return;
        }
        int phase = ShowTimeline.phase();
        int w = g.guiWidth();
        int h = g.guiHeight();
        long ticks = ShowClient.position() / ShowConstants.SAMPLES_PER_TICK;

        // The blackout is the backdrop for the whole opening: the heart pulses on it and the
        // burst explodes on it. The datapack held its title until opening_done, 50 ticks after
        // the drop; here the world only reappears when the song phase takes over.
        if (phase == ShowTimeline.PH_BLACKOUT || phase == ShowTimeline.PH_HEART
                || phase == ShowTimeline.PH_BURST) {
            int a = Math.round(ShowTimeline.blackoutAlpha(ticks) * 255.0F);
            if (a > 0) {
                g.fill(0, 0, w, h, (a << 24));
            }
            if (phase == ShowTimeline.PH_BLACKOUT) {
                return;
            }
        }

        float partial = delta.getGameTimeDeltaPartialTick(true);
        int level = Mth.clamp(Math.round(ShowTimeline.wash(partial)), 0, ShowHudData.WASH_ALPHA.length - 1);
        // The veil is atmosphere, not a blindfold: the baked table's intensity is kept but scaled
        // down so players and strikes stay readable through the red.
        int alpha = Math.round(ShowHudData.WASH_ALPHA[level] * 0.4F);
        if (alpha > 0) {
            g.fill(0, 0, w, h, (alpha << 24) | (WASH_R << 16) | (WASH_G << 8) | WASH_B);
        }

        beginSprites();
        if (phase == ShowTimeline.PH_HEART) {
            // The ring only fills 230x194 of the 256 px cell, so the cell may overflow the screen by
            // that inset: sizing it to 95% of the fit limit grows the heart while the ring stays off
            // the edges. The old title-pose size of 1200 px put the whole ring outside the frame.
            int size = Math.round(Math.min(w * 256.0F / RING_W, h * 256.0F / RING_H) * 0.95F);
            blitTitleSprite(g, HEART, ShowTimeline.heartFrame(ticks), 13, 256, 256, 3328, 256,
                (w - size) / 2, (h - size) / 2, size, size);
        } else if (phase == ShowTimeline.PH_BURST) {
            blitTitleSprite(g, BURST, ShowTimeline.burstFrame(ticks), 16, 256, 128, 4096, 128,
                w / 2 - 2400, h / 2 - 1200, 4800, 2400);
        }
        // The bar is crisp UI, so it rides above the veil instead of being tinted by it.
        if (phase == ShowTimeline.PH_SONG && ShowBoss.visible()) {
            drawBossBar(g, partial);
        }
    }

    /**
     * A {@code fill} tears its render type down with blending switched off, and GuiGraphics.blit
     * does not re-arm it, so every sprite would land with its RGB written straight over the screen:
     * the heart's soft 1-8 alpha fringe became solid blocks. Re-enable the heap blend for sprites.
     */
    private static void beginSprites() {
        RenderSystem.enableBlend();
        RenderSystem.defaultBlendFunc();
    }

    /** The title pose draws a shadow pass one font pixel down-right, then the ink pass over it. */
    private static void blitTitleSprite(GuiGraphics g, ResourceLocation atlas, int frame, int cols,
                                        int cellW, int cellH, int texW, int texH,
                                        int x, int y, int drawW, int drawH) {
        int u = (frame % cols) * cellW;
        int v = (frame / cols) * cellH;
        g.setColor(0.25F, 0.25F, 0.25F, 1.0F);
        g.blit(atlas, x + SHADOW_OFFSET, y + SHADOW_OFFSET, drawW, drawH, u, v, cellW, cellH, texW, texH);
        g.setColor(1.0F, 1.0F, 1.0F, 1.0F);
        g.blit(atlas, x, y, drawW, drawH, u, v, cellW, cellH, texW, texH);
    }

    // ------------------------------------------------------------------ HUD layer

    public static void renderHud(GuiGraphics g, DeltaTracker delta) {
        if (!ShowTimeline.active()) {
            return;
        }
        int phase = ShowTimeline.phase();
        if (phase == ShowTimeline.PH_SONG || phase == ShowTimeline.PH_BURST) {
            drumCorners(g, delta);
        }
        beginSprites();
        if (phase == ShowTimeline.PH_CLOSING) {
            int ct = ShowTimeline.closingTick();
            if (ct < 40) {
                drawFullHud(g, ShowTimeline.closingPreset(), ShowTimeline.closingFrame(), RED,
                    ShowTimeline.closingMin(), ShowTimeline.closingS10(), ShowTimeline.closingS1(), -1);
            } else if (ct < 56) {
                drawCollapse(g, ct);
            }
            return;
        }
        if (phase != ShowTimeline.PH_BURST && phase != ShowTimeline.PH_SONG) {
            return;
        }
        int preset = ShowTimeline.hudPreset();
        int mode = ShowHudData.P_MODE[preset];
        int lyric = ShowTimeline.lyricCell();
        if (mode == 0) {
            drawFullHud(g, preset, ShowTimeline.discFrame(), ShowHudData.P_TC[preset],
                ShowTimeline.dispMin(), ShowTimeline.dispS10(), ShowTimeline.dispS1(), lyric);
        } else if (mode == 1) {
            drawBoxHud(g, preset, lyric);
        } else {
            drawLyricOnly(g, lyric);
        }
        if (phase == ShowTimeline.PH_SONG) {
            ShowStrikeRender.renderHud(g);
        }
    }

    /**
     * The drum's own light. Four corner washes, not a vignette: each corner is a stack of squares
     * that fades toward the middle, so the screen reads as four soft red lamps breathing with the
     * kick. The level is read from the baked drum envelope at the sample actually being heard, and
     * the peak is deliberately low - a hint of red, never a flashbang.
     */
    private static void drumCorners(GuiGraphics g, DeltaTracker delta) {
        float pulse = ShowDrum.pulse(delta.getGameTimeDeltaPartialTick(true));
        if (pulse <= 0.02F) {
            return;
        }
        int w = g.guiWidth();
        int h = g.guiHeight();
        int reach = Math.max(24, Math.round(Math.min(w, h) * 0.26F));
        int peak = Math.round(4.0F + 16.0F * pulse);
        int steps = 12;
        int band = Math.max(1, Math.round(peak / (float) steps));
        int color = (band << 24) | 0xC2160C;
        for (int k = steps; k >= 1; k--) {
            int size = reach * k / steps;
            g.fill(0, 0, size, size, color);
            g.fill(w - size, 0, w, size, color);
            g.fill(0, h - size, size, h, color);
            g.fill(w - size, h - size, w, h, color);
        }
    }

    /**
     * The RONOVA reveal: molten fill eased to the target's live health inside the gothic frame, the
     * wordmark above, and the possessed player's name and hp below. The dog mod's health mechanic
     * with a molten twist: ember notch slashes flare white-hot as the fill sweeps past and cool to
     * scars, hits kick the bar and big hits shake it, the player's own hurt flashes the frame white,
     * half health breaks the seal into a crimson phase II, and death draws an ECG flatline. Only the
     * song phase - the boss appears when the heart bursts, so the bar must not preempt the cutscene.
     *
     * <p>Dressing: the frame's own silhouette blooms softly behind it, an enchanted-glint sheen
     * crosses the lit fill, and the wordmark is a living surface - it glints on the same clock,
     * burns crimson with the seal and flares on a big hit. The sheen rides the show clock, so it
     * freezes with the song.
     */
    private static void drawBossBar(GuiGraphics g, float partial) {
        int w = g.guiWidth();
        // Fixed physical footprint: logical size shrinks as GUI scale rises, so a scale-4
        // player gets a compact bar instead of one four times the scale-1 bar.
        float scale = (float) Math.max(1.0, Minecraft.getInstance().getWindow().getGuiScale());
        int barW = Math.min(Math.min(w - 32, 420), Math.round(560.0F / scale));
        int barH = Math.round(barW * (float) BOSS_TEX_H / BOSS_TEX_W);
        // Recoil and shake offset the coordinates directly, not the pose: scissors are screen-space
        // and would not follow a pose translate, so the fill clip would slip off the moving frame.
        long now = System.currentTimeMillis();
        int dx = Math.round(ShowBoss.recoil() * barW / 186.0F);
        int dy = 0;
        long bigAge = ShowBoss.bigHitAge();
        if (bigAge >= 0L && bigAge < 400L) {
            float decay = 1.0F - bigAge / 400.0F;
            long step = bigAge / 40L;
            dx += Math.round(((step * 73L) % 5L - 2L) * decay);
            dy = Math.round(((step * 37L) % 3L - 1L) * decay);
        }
        int x = (w - barW) / 2 + dx;
        int nameW = Math.min(Math.round(barW * 0.45F), 162);
        int nameH = Math.round(nameW * 26.0F / 162.0F);
        int nameY = 2;
        int y = nameY + nameH + 4 + dy;

        int fx = x + Math.round(barW * BOSS_FILL_X0 / (float) BOSS_TEX_W);
        int fy = y + Math.round(barH * BOSS_FILL_Y0 / (float) BOSS_TEX_H);
        int fw = Math.round(barW * (BOSS_FILL_X1 - BOSS_FILL_X0) / (float) BOSS_TEX_W);
        int fh = Math.round(barH * (BOSS_FILL_Y1 - BOSS_FILL_Y0) / (float) BOSS_TEX_H);
        int fillW = Math.round(fw * Mth.clamp(ShowBoss.fill(), 0.0F, 100.0F) / 100.0F);
        int ghostW = Math.round(fw * Mth.clamp(ShowBoss.ghostFill(), 0.0F, 100.0F) / 100.0F);
        float smooth = ShowClient.position() / (float) ShowConstants.SAMPLES_PER_TICK + partial;
        // The bloom follows the frame's silhouette, so it never shows the texture quad as a panel.
        float breath = 0.5F + 0.5F * Mth.sin(smooth * 0.055F);
        boolean phase2 = ShowBoss.phase2();
        bloom(g, x, y, barW, barH, phase2 ? 0.30F + 0.26F * breath : 0.14F + 0.05F * breath,
            phase2 ? 0xE02810 : 0xC2531F);
        if (ShowBoss.frameFlash() > 0.0F) {
            bloom(g, x, y, barW, barH, 0.55F * ShowBoss.frameFlash(), 0xFFF3E0);
        }
        if (ShowBoss.dead()) {
            drawFlatline(g, fx, fy, fw, fh);
        } else {
            // The health just lost lingers as a translucent trail behind the live edge, then shrinks away.
            if (ghostW > fillW) {
                g.enableScissor(fx + fillW, fy, fx + ghostW, fy + fh);
                g.setColor(1.0F, 1.0F, 1.0F, 0.45F);
                g.blit(BOSS_FILL, fx, fy, fw, fh, 0, 0, 970, 118, 970, 118);
                g.setColor(1.0F, 1.0F, 1.0F, 1.0F);
                g.disableScissor();
            }
            if (fillW > 0) {
                g.enableScissor(fx, fy, fx + fillW, fy + fh);
                g.blit(BOSS_FILL, fx, fy, fw, fh, 0, 0, 970, 118, 970, 118);
                if (ShowBoss.phase2()) {
                    // The broken seal burns crimson instead of molten orange, fractures crawling with it.
                    g.fill(fx, fy, fx + fillW, fy + fh, 0xB4D01808);
                    drawCracks(g, fx, fy, fillW, fh);
                }
                if (ShowBoss.phaseFlash()) {
                    g.fill(fx, fy, fx + fillW, fy + fh, 0xB4FFF3E0);
                }
                g.disableScissor();
                float flash = ShowBoss.flashAlpha();
                if (flash > 0.0F) {
                    g.fill(fx, fy, fx + fillW, fy + fh, ((int) (150 * flash) << 24) | 0xFFFFFF);
                }
                if (ShowBoss.recoilHot() && fillW > 1) {
                    g.fill(fx + fillW - 2, fy, fx + fillW, fy + fh, 0xC8FFF3E0);
                }
                if (ShowBoss.low()) {
                    float pulse = 0.5F + 0.5F * Mth.sin((now % 800L) / 800.0F * 2.0F * (float) Math.PI);
                    g.fill(fx, fy, fx + fillW, fy + fh, ((int) (80 * pulse) << 24) | 0xFF2010);
                }
            }
        }
        if (!ShowBoss.dead() && fillW > 8) {
            sheen(g, fx, fy, fillW, fh, smooth);
            // A lit lip along the top and a shadow along the bottom round the molten well, so the
            // fill reads as liquid inside the frame instead of a flat strip.
            beginSprites();
            g.fill(fx, fy, fx + fillW, fy + Math.max(1, fh / 16), 0x26FFF2E0);
            g.fill(fx, fy + fh - Math.max(1, fh / 10), fx + fillW, fy + fh, 0x3A120300);
        }
        drawNotches(g, fx, fy, fw, fh, now);
        // fill() leaves blending off; the frame and wordmark have transparent texels that need it back.
        beginSprites();
        g.blit(BOSS_FRAME, x, y, barW, barH, 0, 0, BOSS_TEX_W, BOSS_TEX_H, BOSS_TEX_W, BOSS_TEX_H);

        if (ShowBoss.phase2() && !ShowBoss.dead()) {
            // The seal-break keeps the frame smouldering, slower and deeper than the low-health
            // throb. Tinting the sprite itself (rather than filling the border rects) keeps the
            // heat on the metal; the transparent hollow and margins stay empty.
            g.setColor(1.0F, 0.34F, 0.24F, 1.0F);
            g.blit(BOSS_FRAME, x, y, barW, barH, 0, 0, BOSS_TEX_W, BOSS_TEX_H, BOSS_TEX_W, BOSS_TEX_H);
            g.setColor(1.0F, 1.0F, 1.0F, 1.0F);
        } else if (ShowBoss.low() && !ShowBoss.dead()) {
            float pulse = 0.5F + 0.5F * Mth.sin((now % 800L) / 800.0F * 2.0F * (float) Math.PI);
            g.setColor(1.0F, 1.0F - 0.5F * pulse, 1.0F - 0.6F * pulse, 1.0F);
            g.blit(BOSS_FRAME, x, y, barW, barH, 0, 0, BOSS_TEX_W, BOSS_TEX_H, BOSS_TEX_W, BOSS_TEX_H);
            g.setColor(1.0F, 1.0F, 1.0F, 1.0F);
        }
        // Those blits leave blending on; the wordmark's transparent texels rely on it too.
        drawWordmark(g, (w - nameW) / 2 + dx, nameY, nameW, nameH, smooth);

        if (!ShowBoss.target().isEmpty()) {
            var font = Minecraft.getInstance().font;
            boolean dead = ShowBoss.hp() <= 0;
            String sub;
            int subColor;
            if (dead) {
                sub = "< " + ShowBoss.target() + " > DEFEATED";
                subColor = 0xD04545;
            } else if (ShowBoss.phase2()) {
                sub = "< " + ShowBoss.target() + " > " + ShowBoss.hp() + "% - MOLTEN";
                subColor = 0xE06A38;
            } else {
                sub = "< " + ShowBoss.target() + " > " + ShowBoss.hp() + "%";
                subColor = 0xB0B0B0;
            }
            int sw = font.width(sub);
            int sy = y + barH + 2;
            g.drawString(font, sub, (w - sw) / 2 + 1, sy + 1, 0x300000, false);
            g.drawString(font, sub, (w - sw) / 2, sy, subColor, false);
        }
    }

    /**
     * A soft ember bloom behind the bar. The sprite is the frame's own alpha, blurred and padded, so
     * the light hugs the gothic silhouette - wings, notches and all - instead of outlining the
     * texture quad. Colour and strength are the caller's: ember while whole, crimson once the seal
     * breaks, white for the hit flash.
     */
    private static void bloom(GuiGraphics g, int x, int y, int barW, int barH, float alpha, int rgb) {
        int padX = Math.round(BOSS_GLOW_PAD * barW / (float) BOSS_TEX_W);
        int padY = Math.round(BOSS_GLOW_PAD * barH / (float) BOSS_TEX_H);
        beginSprites();
        g.setColor(((rgb >> 16) & 0xFF) / 255.0F, ((rgb >> 8) & 0xFF) / 255.0F,
            (rgb & 0xFF) / 255.0F, alpha);
        g.blit(BOSS_GLOW, x - padX, y - padY, barW + 2 * padX, barH + 2 * padY,
            0, 0, BOSS_GLOW_W, BOSS_GLOW_H, BOSS_GLOW_W, BOSS_GLOW_H);
        g.setColor(1.0F, 1.0F, 1.0F, 1.0F);
    }

    /**
     * Enchanted-glint sheen: a feathered warm band crosses the lit fill every few seconds. It reads
     * the show clock, so it freezes on pause and resumes with the song instead of running on wall time.
     */
    private static void sheen(GuiGraphics g, int fx, int fy, int fillW, int fh, float smooth) {
        float cycle = smooth % 118.0F;
        if (cycle > 46.0F) {
            return;
        }
        int band = fx - 26 + Math.round((fillW + 52) * (cycle / 46.0F));
        int[] widths = {30, 16, 6};
        int[] alphas = {11, 20, 34};
        for (int i = 0; i < widths.length; i++) {
            int x0 = Math.max(fx, band - widths[i] / 2);
            int x1 = Math.min(fx + fillW, band + widths[i] / 2 + 1);
            if (x1 <= x0) {
                continue;
            }
            g.enableScissor(x0, fy, x1, fy + fh);
            g.fill(fx, fy, fx + fillW, fy + fh, (alphas[i] << 24) | 0xFFF0E4);
            g.disableScissor();
        }
    }

    /**
     * The RONOVA wordmark as a living surface: a crimson aura behind the glyphs, a tint that turns
     * the letters crimson when the seal breaks and flares on a big hit, and a gold glint of its own
     * on the show clock.
     */
    private static void drawWordmark(GuiGraphics g, int nx, int nameY, int nameW, int nameH, float smooth) {
        boolean phase2 = ShowBoss.phase2();
        long bigAge = ShowBoss.bigHitAge();
        float flare = bigAge >= 0L && bigAge < 400L ? 1.0F - bigAge / 400.0F : 0.0F;
        g.setColor(1.0F, 0.18F, 0.10F, 0.35F);
        g.blit(BOSS_NAME, nx - 2, nameY - 1, nameW + 4, nameH + 2, 0, 0, 162, 26, 162, 26);
        float lift = 1.0F + 0.45F * flare;
        g.setColor(lift, lift * (phase2 ? 0.42F : 1.0F), lift * (phase2 ? 0.36F : 1.0F), 1.0F);
        g.blit(BOSS_NAME, nx, nameY, nameW, nameH, 0, 0, 162, 26, 162, 26);
        float cycle = smooth % 92.0F;
        if (cycle < 28.0F) {
            int band = nx - 22 + Math.round((nameW + 44) * (cycle / 28.0F));
            int[] widths = {20, 10};
            for (int i = 0; i < widths.length; i++) {
                int x0 = Math.max(nx, band - widths[i] / 2);
                int x1 = Math.min(nx + nameW, band + widths[i] / 2 + 1);
                if (x1 <= x0) {
                    continue;
                }
                float hot = i == 1 ? 1.35F : 1.12F;
                g.enableScissor(x0, nameY - 2, x1, nameY + nameH + 2);
                g.setColor(hot, hot * (phase2 ? 0.50F : 0.94F), hot * (phase2 ? 0.45F : 0.78F), 1.0F);
                g.blit(BOSS_NAME, nx, nameY, nameW, nameH, 0, 0, 162, 26, 162, 26);
                g.disableScissor();
            }
        }
        g.setColor(1.0F, 1.0F, 1.0F, 1.0F);
    }

    /**
     * Ten segments, nine slashes: the dog's alternating lean, cut as gothic tick marks across the
     * hollow. A crossed notch flares white-hot for 250 ms, cools to ember over 600 ms, then keeps
     * the scar; an un-crossed one waits as a dark score mark. Healing re-arms the scars.
     */
    private static void drawNotches(GuiGraphics g, int fx, int fy, int fw, int fh, long now) {
        int n = ShowBoss.notchCount();
        for (int i = 1; i < n; i++) {
            int nx = fx + fw * i / n;
            int lean = (i % 2 == 0) ? 2 : -2;
            int color;
            int alpha;
            if (ShowBoss.notchCrossed(i)) {
                long age = now - ShowBoss.notchFlareMs(i);
                if (age < 250L) {
                    color = 0xFFF3E0;
                    alpha = 255;
                } else if (age < 850L) {
                    float t = (age - 250L) / 600.0F;
                    color = lerpColor(0xFFF3E0, 0xFF5A1F, t);
                    alpha = Math.round(Mth.lerp(t, 255.0F, 140.0F));
                } else {
                    color = 0xFF5A1F;
                    alpha = 140;
                }
            } else {
                color = 0x2A1008;
                alpha = 110;
            }
            slash(g, nx, fy - 1, nx + lean, fy + fh + 1, (alpha << 24) | color);
        }
    }

    /** Phase II fractures: three deterministic jagged cracks crawling down the crimson fill. */
    private static void drawCracks(GuiGraphics g, int fx, int fy, int fillW, int fh) {
        long age = ShowBoss.phase2Age();
        int alpha = Math.round(160 * Mth.clamp(age / 300.0F, 0.0F, 1.0F));
        if (alpha <= 0) {
            return;
        }
        int color = (alpha << 24) | 0x1A0602;
        float[] at = {0.22F, 0.55F, 0.78F};
        for (int c = 0; c < at.length; c++) {
            int cx = fx + Math.round(fillW * at[c]);
            if (cx >= fx + fillW - 2) {
                continue;
            }
            int xx = cx;
            int yy = fy;
            int seg = 0;
            while (yy < fy + fh) {
                int ny = Math.min(fy + fh, yy + 4 + seg % 3);
                int nx = cx + (seg * 7 + c * 5) % 5 - 2;
                slash(g, xx, yy, nx, ny, color);
                xx = nx;
                yy = ny;
                seg++;
            }
        }
    }

    /** Death: the molten fill chars over and an ember ECG line goes flat, its last blip fading. */
    private static void drawFlatline(GuiGraphics g, int fx, int fy, int fw, int fh) {
        g.fill(fx, fy, fx + fw, fy + fh, 0xC8140806);
        long age = ShowBoss.deathAge();
        int mid = fy + fh / 2;
        int alpha = age >= 0L && age < 2000L ? 230 : 170;
        int color = (alpha << 24) | 0xFF5A1F;
        g.fill(fx + 2, mid, fx + fw - 2, mid + 1, color);
        if (age >= 0L && age < 1200L) {
            int bx = fx + fw * 2 / 3;
            int h = Math.round((1.0F - age / 1200.0F) * (fh / 3.0F));
            if (h > 0) {
                slash(g, bx - 3, mid, bx, mid - h, color);
                slash(g, bx, mid - h, bx + 3, mid, color);
            }
        }
    }

    /** A one-pixel Bresenham-ish run: GuiGraphics has no line primitive, fill is the pen. */
    private static void slash(GuiGraphics g, int x1, int y1, int x2, int y2, int color) {
        int steps = Math.max(1, y2 - y1);
        for (int yy = y1; yy <= y2; yy++) {
            int xx = x1 + Math.round((x2 - x1) * (yy - y1) / (float) steps);
            g.fill(xx, yy, xx + 1, yy + 1, color);
        }
    }

    private static int lerpColor(int a, int b, float t) {
        int r = Math.round(Mth.lerp(t, (a >> 16) & 0xFF, (b >> 16) & 0xFF));
        int gg = Math.round(Mth.lerp(t, (a >> 8) & 0xFF, (b >> 8) & 0xFF));
        int bb = Math.round(Mth.lerp(t, a & 0xFF, b & 0xFF));
        return (r << 16) | (gg << 8) | bb;
    }

    /** Mode 0: pad, box, disc, timer, lyric - the full bar, with the preset's glitch offsets. */
    private static void drawFullHud(GuiGraphics g, int p, int disc, int timerColor,
                                    int min, int s10, int s1, int lyric) {
        int bx = ShowHudData.P_BX[p];
        int df = ShowHudData.P_DF[p];
        int timerAdv = ShowHudData.DIGIT_ADV[min] + ShowHudData.DIGIT_ADV[10]
            + ShowHudData.DIGIT_ADV[s10] + ShowHudData.DIGIT_ADV[s1] + ShowHudData.TIME_SUFFIX_ADV;
        int width = 139 + ShowHudData.P_BSP[p] + ShowHudData.BOX_ADV[bx] + ShowHudData.P_BSN[p]
            - 88 + ShowHudData.P_DSP[p] + ShowHudData.DISC_ADV[df][disc] + ShowHudData.P_DSN[p]
            + 3 + ShowHudData.P_TSP[p] + timerAdv + ShowHudData.P_TSN[p]
            - 230 - 232 + ShowHudData.LYRIC_ADV[0] - 88;
        int pen = (g.guiWidth() - width) / 2;
        int y = barY(g);

        pen += 139 + ShowHudData.P_BSP[p];
        blitBox(g, pen, bx);
        pen += ShowHudData.BOX_ADV[bx] + ShowHudData.P_BSN[p] - 88 + ShowHudData.P_DSP[p];
        blitDisc(g, pen, df, disc);
        pen += ShowHudData.DISC_ADV[df][disc] + ShowHudData.P_DSN[p] + 3 + ShowHudData.P_TSP[p];
        pen = drawTimer(g, pen, min, s10, s1, timerColor);
        pen += ShowHudData.P_TSN[p] - 230 - 232;
        blitLyric(g, pen, lyric);
    }

    /** Mode 1: the box and the lyric, no disc or timer (preset 5's standalone-word frame). */
    private static void drawBoxHud(GuiGraphics g, int p, int lyric) {
        int bx = ShowHudData.P_BX[p];
        int width = 139 + ShowHudData.P_BSP[p] + ShowHudData.BOX_ADV[bx] + ShowHudData.P_BSN[p]
            - 236 - 232 + ShowHudData.LYRIC_ADV[0] - 88;
        int pen = (g.guiWidth() - width) / 2;
        pen += 139 + ShowHudData.P_BSP[p];
        blitBox(g, pen, bx);
        pen += ShowHudData.BOX_ADV[bx] + ShowHudData.P_BSN[p] - 236 - 232;
        blitLyric(g, pen, lyric);
    }

    /** Mode 2: just the lyric, on the shipped lyric_only pads (preset 8). */
    private static void drawLyricOnly(GuiGraphics g, int lyric) {
        int width = -236 + ShowHudData.LYRIC_ADV[0] - 88;
        int pen = (g.guiWidth() - width) / 2;
        pen += -236;
        blitLyric(g, pen, lyric);
    }

    /** The ending's collapse: the box shrinks through its last cells while disc_c spins down. */
    private static void drawCollapse(GuiGraphics g, int ct) {
        int k = ct - 40;
        int kb = Mth.clamp(k / 2, 0, ShowHudData.COLLAPSE_BOX.length - 1);
        int kd = Mth.clamp(k * 10 / 16, 0, ShowHudData.DISC_C_ADV.length - 1);
        int bx = ShowHudData.COLLAPSE_BOX[kb];
        int width = 139 + ShowHudData.BOX_ADV[bx] - 88 + ShowHudData.DISC_C_ADV[kd] + 3 + 54 - 230;
        int pen = (g.guiWidth() - width) / 2;
        pen += 139;
        blitBox(g, pen, bx);
        pen += ShowHudData.BOX_ADV[bx] - 88;
        blitDiscC(g, pen, kd);
    }

    // ------------------------------------------------------------------ glyph blits

    private static void blitBox(GuiGraphics g, int x, int idx) {
        g.blit(BOX, x, barY(g) + 36, 92, 32, 0, idx * 32, 92, 32, 92, 416);
    }

    private static void blitDisc(GuiGraphics g, int x, int variant, int frame) {
        g.blit(DISC_V[variant], x, barY(g) + 40, 24, 24,
            (frame % 6) * 64, (frame / 6) * 64, 64, 64, 384, 256);
    }

    private static void blitDiscC(GuiGraphics g, int x, int frame) {
        g.blit(DISC_C, x, barY(g) + 40, 24, 24,
            (frame % 5) * 64, (frame / 5) * 64, 64, 64, 320, 128);
    }

    private static void blitLyric(GuiGraphics g, int x, int cell) {
        int c = Math.max(0, cell);
        g.blit(LYRIC, x, barY(g) + 9, 320, 40,
            (c % 6) * 256, (c / 6) * 32, 256, 32, 1536, 2368);
    }

    /** "m:ss / 9:06" in the digits font, tinted by the preset; returns the pen after the suffix. */
    private static int drawTimer(GuiGraphics g, int pen, int min, int s10, int s1, int color) {
        float r = ((color >> 16) & 0xFF) / 255.0F;
        float gg = ((color >> 8) & 0xFF) / 255.0F;
        float b = (color & 0xFF) / 255.0F;
        g.setColor(r, gg, b, 1.0F);
        int y = barY(g) + 48;
        pen = digit(g, pen, y, min);
        pen = digit(g, pen, y, 10);
        pen = digit(g, pen, y, s10);
        pen = digit(g, pen, y, s1);
        pen += 4;
        pen = digit(g, pen, y, 11);
        pen += 4;
        pen = digit(g, pen, y, 9);
        pen = digit(g, pen, y, 10);
        pen = digit(g, pen, y, 0);
        pen = digit(g, pen, y, 6);
        g.setColor(1.0F, 1.0F, 1.0F, 1.0F);
        return pen;
    }

    private static int digit(GuiGraphics g, int pen, int y, int idx) {
        g.blit(DIGITS, pen, y, 8, 8, idx * 8, 0, 8, 8, 96, 8);
        return pen + ShowHudData.DIGIT_ADV[idx];
    }
}