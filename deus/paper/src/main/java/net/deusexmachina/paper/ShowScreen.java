package net.deusexmachina.paper;

import java.util.HashMap;
import java.util.Map;
import java.util.Random;
import java.util.UUID;
import org.bukkit.Bukkit;
import org.bukkit.command.ConsoleCommandSender;
import org.bukkit.entity.Player;

/**
 * The show's screen, ported from the datapack's title/actionbar strings and the mod's
 * ShowTimeline. The wash, heart and burst ride in the title slot; the disc HUD and lyrics
 * ride in the actionbar. Everything is drawn with the resource pack's bitmap fonts, so a
 * vanilla client sees the same show the datapack used to draw.
 */
public final class ShowScreen {
    private static final int PH_IDLE = 0;
    private static final int PH_BLACKOUT = 1;
    private static final int PH_HEART = 2;
    private static final int PH_BURST = 3;
    private static final int PH_SONG = 4;
    private static final int PH_CLOSING = 5;

    private final DeusExPlugin plugin;
    private final Random random = new Random();
    private final Map<UUID, Integer> calloutUntil = new HashMap<>();

    private int phase = PH_IDLE;
    private int wash;
    private int washDrain;
    private int wlast = -1;
    private int flashCountdown = 200;
    private int flashAge = -1;
    private long lcg;

    private int glitchLeft;
    private int hudPreset;
    private int discFrame;
    private int dispMin;
    private int dispS10;
    private int dispS1;
    private long lastHudDraw = -1;
    private int lyricCell = -1;
    private String lastActionbar = "";

    private int closingTick;
    private int closingFrame;
    private int closingPreset;
    private int closingMin;
    private int closingS10;
    private int closingS1;
    private boolean closingCleared;
    private int pausedResend;

    public ShowScreen(DeusExPlugin plugin) {
        this.plugin = plugin;
    }

    private void cmd(String command) {
        ConsoleCommandSender console = Bukkit.getConsoleSender();
        Bukkit.dispatchCommand(console, command);
    }

    private void title(Player player, String json) {
        cmd("title " + player.getName() + " title " + json);
    }

    private void actionbar(Player player, String json) {
        cmd("title " + player.getName() + " actionbar " + json);
        lastActionbar = json;
    }

    private void broadcastTitle(String json) {
        for (Player player : Bukkit.getOnlinePlayers()) {
            title(player, json);
        }
    }

    private void broadcastActionbar(String json) {
        for (Player player : Bukkit.getOnlinePlayers()) {
            actionbar(player, json);
        }
    }

    public void clear(Player player) {
        cmd("title " + player.getName() + " reset");
        cmd("title " + player.getName() + " actionbar {\"text\":\"\"}");
    }

    public void clearAll() {
        for (Player player : Bukkit.getOnlinePlayers()) {
            clear(player);
        }
        lastActionbar = "";
    }

    /** Lock callout: a plain actionbar line that briefly replaces the HUD for the marked player. */
    public void callout(Player player, String text, String color, int tickCount) {
        cmd("title " + player.getName() + " actionbar {\"text\":\"" + text + "\",\"color\":\"" + color + "\",\"bold\":true}");
        calloutUntil.put(player.getUniqueId(), tickCount + 25);
    }

    public void begin() {
        phase = PH_IDLE;
        wash = 0;
        washDrain = 0;
        wlast = -1;
        flashCountdown = 200;
        flashAge = -1;
        glitchLeft = 0;
        hudPreset = 0;
        lastHudDraw = -1;
        lyricCell = -1;
        closingTick = 0;
        closingFrame = 0;
        closingCleared = false;
        calloutUntil.clear();
        for (Player player : Bukkit.getOnlinePlayers()) {
            cmd("title " + player.getName() + " times 0 100000 0");
        }
    }

    public void beginClosing() {
        phase = PH_CLOSING;
        closingTick = 0;
        closingFrame = 0;
        wash = 17;
        wlast = -1;
        washDrain = 0;
        closingCleared = false;
    }

    public void tick(int state, int musicTick, int tickCount) {
        if (state == ShowConstants.STATE_PAUSED) {
            // The actionbar fades on its own; keep the frozen frame alive while paused.
            if (++pausedResend >= 20 && !lastActionbar.isEmpty()) {
                pausedResend = 0;
                broadcastActionbar(lastActionbar);
            }
            return;
        }
        pausedResend = 0;
        if (state == ShowConstants.STATE_CLOSING) {
            tickClosing(tickCount);
            return;
        }
        if (state != ShowConstants.STATE_PLAYING) {
            if (phase != PH_IDLE) {
                phase = PH_IDLE;
                clearAll();
            }
            return;
        }

        int oldPhase = phase;
        if (musicTick < 42) {
            phase = PH_BLACKOUT;
            wash = 0;
            if (oldPhase != PH_BLACKOUT) {
                broadcastTitle(ShowData.T_BLACK);
            }
            return;
        }
        if (musicTick < ShowConstants.DROP_TICKS) {
            phase = PH_HEART;
            int hb = heartAge(musicTick);
            int level = hb < ShowData.HB_WASH.length ? ShowData.HB_WASH[hb] : 0;
            String json = ShowData.T_HEART
                    .replace("$(rc)", redCell(level))
                    .replace("$(heart)", glyph(ShowData.HEART_BASE, Math.min(hb, 12)));
            broadcastTitle(json);
            return;
        }
        if (musicTick < ShowConstants.DROP_TICKS + 50) {
            phase = PH_BURST;
            int k = musicTick - ShowConstants.DROP_TICKS;
            int bf = k <= 0 ? 0 : k == 1 ? 1 : Math.min(15, 2 + (k - 2) / 3);
            wash = Math.min(14, k + 1);
            String json = ShowData.T_BURST
                    .replace("$(rc)", redCell(wash))
                    .replace("$(burst)", glyph(ShowData.BURST_BASE, bf));
            broadcastTitle(json);
            return;
        }

        phase = PH_SONG;
        if (oldPhase == PH_BURST) {
            flashCountdown = 200;
            wlast = -1;
        }
        tickFlashAndWash();
        if (wash != wlast) {
            wlast = wash;
            broadcastTitle(ShowData.T_WASH.replace("$(rc)", redCell(wash)));
        }
        tickHud(musicTick, tickCount);
    }

    /** Hand a joining player the current frame without advancing the shared state. */
    public void syncPlayer(Player player, int state, int musicTick) {
        cmd("title " + player.getName() + " times 0 100000 0");
        if (state != ShowConstants.STATE_PLAYING) {
            return;
        }
        if (musicTick < 42) {
            title(player, ShowData.T_BLACK);
        } else if (musicTick < ShowConstants.DROP_TICKS) {
            int hb = heartAge(musicTick);
            int level = hb < ShowData.HB_WASH.length ? ShowData.HB_WASH[hb] : 0;
            title(player, ShowData.T_HEART
                    .replace("$(rc)", redCell(level))
                    .replace("$(heart)", glyph(ShowData.HEART_BASE, Math.min(hb, 12))));
        } else if (musicTick < ShowConstants.DROP_TICKS + 50) {
            int k = musicTick - ShowConstants.DROP_TICKS;
            int bf = k <= 0 ? 0 : k == 1 ? 1 : Math.min(15, 2 + (k - 2) / 3);
            title(player, ShowData.T_BURST
                    .replace("$(rc)", redCell(Math.min(14, k + 1)))
                    .replace("$(burst)", glyph(ShowData.BURST_BASE, bf)));
        } else {
            title(player, ShowData.T_WASH.replace("$(rc)", redCell(wash)));
            if (!lastActionbar.isEmpty()) {
                actionbar(player, lastActionbar);
            }
        }
    }

    private static int heartAge(int ticks) {
        int hb = 99;
        for (int i = ShowData.BEAT_TICKS.length - 1; i >= 0; i--) {
            if (ticks >= ShowData.BEAT_TICKS[i]) {
                hb = ticks - ShowData.BEAT_TICKS[i];
                break;
            }
        }
        return Math.min(hb, 99);
    }

    private void tickFlashAndWash() {
        if (flashAge >= 0) {
            flashAge++;
            if (flashAge >= 22) {
                flashAge = -1;
            }
        } else {
            flashCountdown--;
            if (flashCountdown <= 0) {
                flashAge = 0;
                wash = 17;
                washDrain = 0;
                lcg = lcg * 1103515245L + 12345L;
                flashCountdown = (int) Math.floorMod(lcg, 261L) + 160;
            }
        }
        if (wash < 14) {
            wash = Math.min(14, wash + 1);
        } else if (wash > 14) {
            washDrain++;
            if (washDrain >= 4) {
                washDrain = 0;
                wash = Math.max(14, wash - 1);
            }
        }
    }

    private void tickHud(int ticks, int tickCount) {
        long draw = ticks / 2L;
        if (draw != lastHudDraw) {
            lastHudDraw = draw;
            discFrame = (int) Math.floorMod(draw, 24L);
            if (glitchLeft > 0) {
                glitchLeft--;
                hudPreset = 1 + random.nextInt(10);
            } else if (random.nextInt(100) < 5) {
                glitchLeft = 1 + random.nextInt(5);
                hudPreset = 1 + random.nextInt(10);
            } else {
                hudPreset = 0;
            }
            int timeSec = ticks / 20;
            dispMin = timeSec / 60;
            dispS10 = (timeSec % 60) / 10;
            dispS1 = timeSec % 10;
            if (ShowData.P_SCR[hudPreset] == 1) {
                dispMin = random.nextInt(10);
                dispS10 = random.nextInt(6);
                dispS1 = random.nextInt(10);
            }
        }
        lyricCell = lyricAt(ticks);
        String json = hudJson(hudPreset, discFrame, dispMin, dispS10, dispS1, lyricCell,
                ShowData.P_TC[hudPreset]);
        for (Player player : Bukkit.getOnlinePlayers()) {
            Integer until = calloutUntil.get(player.getUniqueId());
            if (until != null && tickCount < until) {
                continue;
            }
            actionbar(player, json);
        }
    }

    private String hudJson(int preset, int frame, int min, int s10, int s1, int lyric, String color) {
        String lyr = lyric >= 0 ? glyph(ShowData.LYRIC_BASE, lyric) : "";
        String g = glyph(ShowData.DISC_V0_BASE, frame);
        int mode = ShowData.P_MODE[preset];
        if (mode == 1) {
            return ShowData.T_BOX
                    .replace("$(bsp)", ShowData.P_BSP[preset])
                    .replace("$(bx)", ShowData.P_BX[preset])
                    .replace("$(bsn)", ShowData.P_BSN[preset])
                    .replace("$(lyr)", lyr);
        }
        if (mode == 2) {
            return ShowData.T_LYRIC.replace("$(lyr)", lyr);
        }
        return ShowData.T_HUD
                .replace("$(bsp)", ShowData.P_BSP[preset])
                .replace("$(bx)", ShowData.P_BX[preset])
                .replace("$(bsn)", ShowData.P_BSN[preset])
                .replace("$(dsp)", ShowData.P_DSP[preset])
                .replace("$(g)", g)
                .replace("$(dsn)", ShowData.P_DSN[preset])
                .replace("$(tsp)", ShowData.P_TSP[preset])
                .replace("$(min)", Integer.toString(min))
                .replace("$(s10)", Integer.toString(s10))
                .replace("$(s1)", Integer.toString(s1))
                .replace("$(tsn)", ShowData.P_TSN[preset])
                .replace("$(lyr)", lyr)
                .replace("$(df)", ShowData.P_DF[preset])
                .replace("$(tc)", color);
    }

    private static int lyricAt(int ticks) {
        for (int i = 0; i < ShowData.LYRIC_START.length; i++) {
            if (ticks >= ShowData.LYRIC_START[i] && ticks < ShowData.LYRIC_END[i]) {
                int le = ticks - ShowData.LYRIC_START[i];
                int rem = ShowData.LYRIC_END[i] - ticks;
                int a = Math.min(5, le);
                int b = Math.min(5, rem * 6 / 8);
                return i * 6 + Math.min(a, b);
            }
        }
        return -1;
    }

    private void tickClosing(int tickCount) {
        closingTick++;
        washDrain++;
        if (washDrain >= 4 && wash > 0) {
            washDrain = 0;
            wash = Math.max(0, wash - 1);
        }
        if (wash != wlast) {
            wlast = wash;
            broadcastTitle(ShowData.T_WASH.replace("$(rc)", redCell(wash)));
        }
        if (closingTick < 40) {
            closingFrame = (closingFrame + 2) % 24;
            closingPreset = 1 + random.nextInt(10);
            closingMin = random.nextInt(10);
            closingS10 = random.nextInt(6);
            closingS1 = random.nextInt(10);
            broadcastActionbar(hudJson(closingPreset, closingFrame, closingMin, closingS10, closingS1,
                    -1, "red"));
        } else if (closingTick < 56) {
            int k = closingTick - 40;
            String json = ShowData.T_COLLAPSE
                    .replace("$(bx)", ShowData.COLLAPSE_BOX[k / 2])
                    .replace("$(g)", ShowData.COLLAPSE_DISC[k * 10 / 16]);
            broadcastActionbar(json);
        }
        if (closingTick >= 56 && wash <= 0 && !closingCleared) {
            closingCleared = true;
            clearAll();
            phase = PH_IDLE;
        }
    }

    private static String redCell(int level) {
        int clamped = Math.max(0, Math.min(ShowData.RED_LV_COUNT - 1, level));
        return glyph(ShowData.RED_LV_BASE, clamped);
    }

    private static String glyph(int base, int index) {
        return Character.toString((char) (base + index));
    }
}