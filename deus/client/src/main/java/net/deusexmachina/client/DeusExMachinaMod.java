package net.deusexmachina.client;

import net.deusexmachina.net.ShowNetwork;
import net.deusexmachina.server.ShowCommands;
import net.deusexmachina.server.ShowOrchestrator;
import net.minecraft.resources.ResourceLocation;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.loading.FMLEnvironment;
import net.neoforged.neoforge.client.event.ClientTickEvent;
import net.neoforged.neoforge.client.event.RegisterGuiLayersEvent;
import net.neoforged.neoforge.client.gui.VanillaGuiLayers;
import net.neoforged.neoforge.common.NeoForge;

/**
 * Entry point. The server half orchestrates the show clock, freeze and weather;
 * the client half owns audio and visuals. The datapack is a scoreboard shim
 * that feeds commands into the orchestrator.
 */
@Mod(DeusExMachinaMod.MODID)
public class DeusExMachinaMod {
    public static final String MODID = "deusexmachina";

    public DeusExMachinaMod(IEventBus modBus) {
        modBus.addListener(ShowNetwork::register);
        NeoForge.EVENT_BUS.addListener(ShowOrchestrator::onServerStarting);
        NeoForge.EVENT_BUS.addListener(ShowOrchestrator::onServerStopped);
        NeoForge.EVENT_BUS.addListener(ShowOrchestrator::onServerTick);
        NeoForge.EVENT_BUS.addListener(ShowOrchestrator::onPlayerLogin);
        NeoForge.EVENT_BUS.addListener(ShowOrchestrator::onPlayerLogout);
        NeoForge.EVENT_BUS.addListener(ShowCommands::register);
        if (FMLEnvironment.dist == Dist.CLIENT) {
            MusicVolume.init();
            modBus.addListener((RegisterGuiLayersEvent event) -> {
                event.registerAbove(VanillaGuiLayers.OVERLAY_MESSAGE,
                    ResourceLocation.fromNamespaceAndPath(MODID, "show_hud"), ShowRender::renderHud);
                event.registerAbove(VanillaGuiLayers.TITLE,
                    ResourceLocation.fromNamespaceAndPath(MODID, "show_wash"), ShowRender::renderWash);
            });
            NeoForge.EVENT_BUS.addListener((ClientTickEvent.Post event) -> {
                ShowClient.tick();
                ShowTimeline.tick();
                ShowBoss.tick();
                ShowStrike.tick();
            });
            NeoForge.EVENT_BUS.addListener(ShowStrikeRender::renderWorld);
            NeoForge.EVENT_BUS.addListener(ShowGlow::renderWorld);
        }
    }
}