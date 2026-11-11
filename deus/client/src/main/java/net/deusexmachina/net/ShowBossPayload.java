package net.deusexmachina.net;

import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.ByteBufCodecs;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/**
 * The RONOVA boss bar config: which player the boss is anchored to and how full the health bar
 * renders (1-100). Pushed on start/stop and to late joiners so the bar always matches the show.
 */
public record ShowBossPayload(boolean visible, String target, int hp, boolean phase2) implements CustomPacketPayload {
    public static final Type<ShowBossPayload> TYPE =
            new Type<>(ResourceLocation.fromNamespaceAndPath("deusexmachina", "show_boss"));
    public static final StreamCodec<RegistryFriendlyByteBuf, ShowBossPayload> CODEC =
            StreamCodec.composite(
                    ByteBufCodecs.BOOL, ShowBossPayload::visible,
                    ByteBufCodecs.STRING_UTF8, ShowBossPayload::target,
                    ByteBufCodecs.VAR_INT, ShowBossPayload::hp,
                    ByteBufCodecs.BOOL, ShowBossPayload::phase2,
                    ShowBossPayload::new);

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
