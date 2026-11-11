package net.deusexmachina.net;

import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.ByteBufCodecs;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/**
 * One charged mark's target. Sent every tick while the warning lives so the sigil follows the
 * target, then pins: {@link #TRACKING} while it follows, {@link #LOCKED} for the last second when
 * it no longer moves, {@link #IMPACT} on the strike frame and {@link #CANCELLED} if the show ends
 * early. Coordinates are the decal centre at the target's feet, except for the seal lance, whose
 * mark sits at the chest.
 *
 * <p>The phase byte packs the attack kind above the state ({@code kind << 2 | state}): plain red
 * bolt, binding grasp, soul siphon, ember barrage or seal lance. That leaves six kind bits, and
 * both sides mask with {@code 0x3F}. Each side derives the radius from the kind, so the payload
 * keeps its six fields.
 */
public record ShowStrikePayload(int id, double x, double y, double z, int ticksLeft,
                                byte phase) implements CustomPacketPayload {
    public static final Type<ShowStrikePayload> TYPE =
            new Type<>(ResourceLocation.fromNamespaceAndPath("deusexmachina", "show_strike"));
    public static final StreamCodec<RegistryFriendlyByteBuf, ShowStrikePayload> CODEC =
            StreamCodec.composite(
                    ByteBufCodecs.VAR_INT, ShowStrikePayload::id,
                    ByteBufCodecs.DOUBLE, ShowStrikePayload::x,
                    ByteBufCodecs.DOUBLE, ShowStrikePayload::y,
                    ByteBufCodecs.DOUBLE, ShowStrikePayload::z,
                    ByteBufCodecs.VAR_INT, ShowStrikePayload::ticksLeft,
                    ByteBufCodecs.BYTE, ShowStrikePayload::phase,
                    ShowStrikePayload::new);

    public static final byte TRACKING = 0;
    public static final byte LOCKED = 1;
    public static final byte IMPACT = 2;
    public static final byte CANCELLED = 3;

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
