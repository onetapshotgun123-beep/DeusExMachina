package net.deusexmachina.net;

import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.ByteBufCodecs;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/**
 * A storm wave has been called: its number, how many players it marked, and who carries the bar.
 * The boss label lets a client show the immunity (the boss is never among the marked) and gives
 * the dev probe something to assert.
 */
public record ShowStormPayload(int wave, int targets, String boss, byte primaryKind,
                               byte secondaryKind) implements CustomPacketPayload {
    public static final Type<ShowStormPayload> TYPE =
            new Type<>(ResourceLocation.fromNamespaceAndPath("deusexmachina", "show_storm"));
    public static final StreamCodec<RegistryFriendlyByteBuf, ShowStormPayload> CODEC =
            StreamCodec.composite(
                    ByteBufCodecs.VAR_INT, ShowStormPayload::wave,
                    ByteBufCodecs.VAR_INT, ShowStormPayload::targets,
                    ByteBufCodecs.STRING_UTF8, ShowStormPayload::boss,
                    ByteBufCodecs.BYTE, ShowStormPayload::primaryKind,
                    ByteBufCodecs.BYTE, ShowStormPayload::secondaryKind,
                    ShowStormPayload::new);

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
