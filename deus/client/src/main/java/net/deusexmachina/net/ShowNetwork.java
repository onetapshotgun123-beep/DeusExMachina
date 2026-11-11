package net.deusexmachina.net;

import net.deusexmachina.server.ShowOrchestrator;
import net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent;
import net.neoforged.neoforge.network.registration.PayloadRegistrar;

/**
 * All payloads are optional: a vanilla client (or a NeoForge client without this jar) ignores them
 * and simply sees no show, which is the trade the rewrite makes - every viewer installs the mod.
 * Marking them required would instead lock such clients out of the server entirely.
 */
public final class ShowNetwork {
    private ShowNetwork() {}

    public static void register(RegisterPayloadHandlersEvent event) {
        PayloadRegistrar registrar = event.registrar("2").optional();
        registrar.playToClient(ShowStatePayload.TYPE, ShowStatePayload.CODEC,
                (payload, context) -> net.deusexmachina.client.ShowClient.handle(payload));
        registrar.playToClient(ShowBossPayload.TYPE, ShowBossPayload.CODEC,
                (payload, context) -> net.deusexmachina.client.ShowBoss.handle(payload));
        registrar.playToClient(ShowStrikePayload.TYPE, ShowStrikePayload.CODEC,
                (payload, context) -> net.deusexmachina.client.ShowStrike.handle(payload));
        registrar.playToClient(ShowStormPayload.TYPE, ShowStormPayload.CODEC,
                (payload, context) -> net.deusexmachina.client.ShowStrike.handleStorm(payload));
        registrar.playToServer(ShowPositionPayload.TYPE, ShowPositionPayload.CODEC,
                (payload, context) -> context.enqueueWork(() -> ShowOrchestrator.reanchor(payload.samples())));
    }
}