package net.deusexmachina.client;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Properties;
import java.util.concurrent.CompletableFuture;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.AbstractSliderButton;
import net.minecraft.client.gui.components.AbstractWidget;
import net.minecraft.client.gui.components.ContainerObjectSelectionList;
import net.minecraft.client.gui.components.OptionsList;
import net.minecraft.client.gui.components.Tooltip;
import net.minecraft.client.gui.components.events.GuiEventListener;
import net.minecraft.client.gui.narration.NarrationElementOutput;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.options.SoundOptionsScreen;
import net.minecraft.client.resources.sounds.Sound;
import net.minecraft.client.resources.sounds.SoundInstance;
import net.minecraft.client.resources.sounds.TickableSoundInstance;
import net.minecraft.client.sounds.AudioStream;
import net.minecraft.client.sounds.SoundBufferLibrary;
import net.minecraft.client.sounds.SoundManager;
import net.minecraft.client.sounds.WeighedSoundEvents;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.neoforged.fml.loading.FMLPaths;
import net.neoforged.neoforge.client.event.ScreenEvent;
import net.neoforged.neoforge.client.event.sound.PlaySoundEvent;
import net.neoforged.neoforge.common.NeoForge;

/**
 * The song volume control.
 *
 * <p>The pack plays its music with {@code /playsound}, so the volume a player hears is
 * {@code instance volume * category volume * master volume}. The datapack writes 1 into the instance
 * volume and cannot read anything back, and the two sliders the game already has are shared with
 * everything else in the world - the song rides the Jukebox slider, which is why turning Music off
 * never silenced it. This class owns the first factor: every {@code deusex:} sound instance is
 * wrapped in one whose volume is the original's times the percentage below, and the percentage is a
 * slider in the game's own Music &amp; Sound screen, in the column under Ambient/Environment.</p>
 */
public final class MusicVolume {
    private static final Logger LOGGER = LoggerFactory.getLogger(DeusExMachinaMod.MODID);
    private static final String NAMESPACE = "deusex";
    private static final String KEY = "song-volume";
    private static final int DEFAULT_PERCENT = 45;
    private static final int COLUMN_WIDTH = 150;

    private static int percent = DEFAULT_PERCENT;
    private static boolean warnedAboutFile;

    private MusicVolume() {}

    public static void init() {
        load();
        NeoForge.EVENT_BUS.addListener(MusicVolume::onScreenInit);
        NeoForge.EVENT_BUS.addListener(MusicVolume::onPlaySound);
    }

    public static int get() {
        return percent;
    }

    public static float scale() {
        return percent / 100.0F;
    }

    private static void set(int value) {
        int clamped = Mth.clamp(value, 0, 100);
        if (clamped == percent) {
            return;
        }
        percent = clamped;
        save();
        applyToPlayingSounds();
    }

    /**
     * Re-reads the volume of everything that is already playing. The engine recomputes each active
     * instance from {@code SoundInstance#getVolume()} whenever a category volume is set, so setting
     * the Jukebox category to the value it already has is what it takes to make a wrapped instance
     * pick up a new percentage mid-song instead of on the next play. The game's own sound sliders do
     * exactly this from their own widgets, on the same thread, which is why it is safe to reach for
     * the menu screen too: RECORDS is the jukebox category and nothing else is listening on it.
     */
    private static void applyToPlayingSounds() {
        Minecraft minecraft = Minecraft.getInstance();
        minecraft.getSoundManager().updateSourceVolume(SoundSource.RECORDS,
                minecraft.options.getSoundSourceVolume(SoundSource.RECORDS));
    }

    private static Path configFile() {
        return FMLPaths.CONFIGDIR.get().resolve(DeusExMachinaMod.MODID + "-client.properties");
    }

    private static void load() {
        Path path = configFile();
        if (!Files.isRegularFile(path)) {
            return;
        }
        Properties properties = new Properties();
        try (InputStream in = Files.newInputStream(path)) {
            properties.load(in);
        } catch (IOException e) {
            warn("could not read " + path, e);
            return;
        }
        String raw = properties.getProperty(KEY);
        if (raw == null) {
            return;
        }
        try {
            percent = Mth.clamp(Integer.parseInt(raw.trim()), 0, 100);
        } catch (NumberFormatException e) {
            warn("ignoring " + KEY + "=" + raw, e);
        }
    }

    private static void save() {
        Properties properties = new Properties();
        properties.setProperty(KEY, Integer.toString(percent));
        try (OutputStream out = Files.newOutputStream(configFile())) {
            properties.store(out, "Deus Ex Machina client settings");
        } catch (IOException e) {
            warn("could not write the song volume", e);
        }
    }

    private static void warn(String what, Throwable e) {
        if (!warnedAboutFile) {
            warnedAboutFile = true;
            LOGGER.warn("Deus Ex Machina: " + what, e);
        }
    }

    private static void onPlaySound(PlaySoundEvent event) {
        SoundInstance sound = event.getSound();
        if (sound == null || sound instanceof Scaled || sound instanceof ShowSound) {
            return;
        }
        ResourceLocation id = sound.getLocation();
        if (id != null && (NAMESPACE.equals(id.getNamespace()) || DeusExMachinaMod.MODID.equals(id.getNamespace()))) {
            event.setSound(sound instanceof TickableSoundInstance ? new ScaledTickable(sound) : new Scaled(sound));
        }
    }

    private static void onScreenInit(ScreenEvent.Init.Post event) {
        Screen screen = event.getScreen();
        if (!(screen instanceof SoundOptionsScreen)) {
            return;
        }
        // The list lays its rows out itself: every render, Entry.render repositions the children of
        // each row (OptionsList.Entry.render, first child in the left column, second in the right),
        // so a row rebuilt here scrolls, resizes and narrates with the vanilla sliders instead of
        // being pasted over them.
        for (GuiEventListener listener : event.getListenersList()) {
            if (!(listener instanceof OptionsList list)) {
                continue;
            }
            boolean alreadyThere = false;
            // OptionsList.Entry itself is protected, but its public parent type is not - the scan
            // goes through ContainerObjectSelectionList.Entry so no inaccessible type is named.
            for (ContainerObjectSelectionList.Entry<?> entry : list.children()) {
                for (GuiEventListener child : entry.children()) {
                    if (child instanceof Slider) {
                        alreadyThere = true;
                    }
                }
            }
            if (!alreadyThere) {
                @SuppressWarnings("unchecked")
                List<ContainerObjectSelectionList.Entry<?>> rows =
                        (List<ContainerObjectSelectionList.Entry<?>>) (List<?>) list.children();
                // Nine categories pair into four rows and a leftover: Voice/Speech sits alone in
                // the left column of the row under Players|Ambient/Environment. The slider takes
                // that row's empty right cell - under Ambient/Environment as asked - without adding
                // a row of its own, which would leave a hole in the left column and push
                // Voice/Speech out of line. The row is rebuilt around the same widget instance, so
                // its option binding, tooltip and immediate apply all survive the move.
                String voice = Component.translatable("soundCategory.voice").getString();
                int voiceRow = -1;
                AbstractWidget voiceWidget = null;
                for (int i = 0; i < rows.size(); i++) {
                    List<? extends GuiEventListener> kids = rows.get(i).children();
                    if (kids.size() == 1 && kids.get(0) instanceof AbstractWidget widget
                            && widget.getMessage().getString().startsWith(voice)) {
                        voiceRow = i;
                        voiceWidget = widget;
                    }
                }
                if (voiceWidget != null) {
                    rows.remove(voiceRow);
                    list.addSmall(voiceWidget, new Slider(COLUMN_WIDTH));
                    rows.add(voiceRow, rows.remove(rows.size() - 1));
                } else {
                    // No lone voice row (a modded screen): fall back to a row of our own under the
                    // ambient slider, invisible left cell and all.
                    list.addSmall(new Spacer(), new Slider(COLUMN_WIDTH));
                    String ambient = Component.translatable("soundCategory.ambient").getString();
                    int below = -1;
                    for (int i = 0; i < rows.size(); i++) {
                        for (GuiEventListener child : rows.get(i).children()) {
                            if (child instanceof AbstractWidget widget
                                    && widget.getMessage().getString().startsWith(ambient)) {
                                below = i + 1;
                            }
                        }
                    }
                    if (below >= 0 && below < rows.size() - 1) {
                        rows.add(below, rows.remove(rows.size() - 1));
                    }
                }
            }
        }
    }

    /** The empty left cell of the slider's row - see onScreenInit for why the row answers two children. */
    private static final class Spacer extends AbstractWidget {
        private Spacer() {
            super(0, 0, COLUMN_WIDTH, 20, Component.empty());
            this.active = false;
        }

        @Override
        protected void renderWidget(GuiGraphics guiGraphics, int mouseX, int mouseY, float partialTick) {
        }

        @Override
        protected void updateWidgetNarration(NarrationElementOutput narrationElementOutput) {
        }
    }

    /** The label reads the stored percentage, so a rebuilt screen shows the setting, not the drag. */
    private static final class Slider extends AbstractSliderButton {
        private Slider(int width) {
            super(0, 0, width, 20, Component.literal("Deus Ex music"), percent / 100.0);
            this.setTooltip(Tooltip.create(Component.literal(
                    "Volume of the Deus Ex Machina song and its intro, on top of the game's own"
                            + " master and Jukebox volumes. Applies as soon as you move it.")));
            this.updateMessage();
        }

        @Override
        protected void updateMessage() {
            String full = "Deus Ex music: " + percent + "%";
            // The cell is 150 pixels, the label about 102 plus the widget's own padding, so the full
            // label always fits on the Music & Sound screen and no short form is needed.
            this.setMessage(Component.literal(full));
        }

        @Override
        protected void applyValue() {
            set((int) Math.round(this.value * 100.0));
        }
    }

    /**
     * Forwards everything about the sound the datapack asked for except its volume, which it takes
     * from {@link MusicVolume} at the moment the engine asks - that is what keeps a running track in
     * step with the slider.
     */
    static class Scaled implements SoundInstance {
        protected final SoundInstance delegate;

        Scaled(SoundInstance delegate) {
            this.delegate = delegate;
        }

        @Override
        public float getVolume() {
            return delegate.getVolume() * scale();
        }

        @Override
        public ResourceLocation getLocation() {
            return delegate.getLocation();
        }

        @Override
        public WeighedSoundEvents resolve(SoundManager manager) {
            return delegate.resolve(manager);
        }

        @Override
        public Sound getSound() {
            return delegate.getSound();
        }

        @Override
        public SoundSource getSource() {
            return delegate.getSource();
        }

        @Override
        public boolean isLooping() {
            return delegate.isLooping();
        }

        @Override
        public boolean isRelative() {
            return delegate.isRelative();
        }

        @Override
        public int getDelay() {
            return delegate.getDelay();
        }

        @Override
        public float getPitch() {
            return delegate.getPitch();
        }

        @Override
        public double getX() {
            return delegate.getX();
        }

        @Override
        public double getY() {
            return delegate.getY();
        }

        @Override
        public double getZ() {
            return delegate.getZ();
        }

        @Override
        public Attenuation getAttenuation() {
            return delegate.getAttenuation();
        }

        @Override
        public boolean canStartSilent() {
            return delegate.canStartSilent();
        }

        @Override
        public boolean canPlaySound() {
            return delegate.canPlaySound();
        }

        @Override
        public CompletableFuture<AudioStream> getStream(SoundBufferLibrary soundBuffers, Sound sound, boolean looping) {
            return delegate.getStream(soundBuffers, sound, looping);
        }
    }

    /**
     * The same, for instances the engine ticks. Handing a ticking sound over as a plain instance
     * would drop it out of the engine's ticking list, so its position and its stop would no longer
     * be reported.
     */
    private static final class ScaledTickable extends Scaled implements TickableSoundInstance {
        private ScaledTickable(SoundInstance delegate) {
            super(delegate);
        }

        @Override
        public void tick() {
            ((TickableSoundInstance) delegate).tick();
        }

        @Override
        public boolean isStopped() {
            return ((TickableSoundInstance) delegate).isStopped();
        }
    }
}
