package net.deusexmachina.net;

import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.ByteBufCodecs;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/**
 * The server's whole vocabulary: what the show is doing and, when that matters, which sample of the
 * song the clients should be hearing. Positions are absolute samples from the head of main_track so
 * a rejoining client can seek straight to them.
 */
public record ShowStatePayload(byte action, long position) implements CustomPacketPayload {
    public static final Type<ShowStatePayload> TYPE =
            new Type<>(ResourceLocation.fromNamespaceAndPath("deusexmachina", "show_state"));
    public static final StreamCodec<RegistryFriendlyByteBuf, ShowStatePayload> CODEC =
            StreamCodec.composite(
                    ByteBufCodecs.BYTE, ShowStatePayload::action,
                    ByteBufCodecs.VAR_LONG, ShowStatePayload::position,
                    ShowStatePayload::new);

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}