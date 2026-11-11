package net.deusexmachina.net;

import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.ByteBufCodecs;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/**
 * A client telling the server where its heard audio actually is. The server re-anchors its own
 * clock to these, which is what keeps a paused singleplayer game, a lagging server and a rejoining
 * player all on the same sample: the audio pipeline, not the tick loop, is the reference.
 */
public record ShowPositionPayload(long samples) implements CustomPacketPayload {
    public static final Type<ShowPositionPayload> TYPE =
            new Type<>(ResourceLocation.fromNamespaceAndPath("deusexmachina", "show_position"));
    public static final StreamCodec<RegistryFriendlyByteBuf, ShowPositionPayload> CODEC =
            StreamCodec.composite(ByteBufCodecs.VAR_LONG, ShowPositionPayload::samples, ShowPositionPayload::new);

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}