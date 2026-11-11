package net.deusexmachina.server;

import com.mojang.brigadier.arguments.IntegerArgumentType;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.EntityArgument;
import net.neoforged.neoforge.event.RegisterCommandsEvent;

/**
 * Player-facing show commands. The boss-bar variant of start needs the target player and the
 * RONOVA bar's hp (1-100); the bare shim functions keep working without them.
 */
public final class ShowCommands {
    private ShowCommands() {
    }

    public static void register(RegisterCommandsEvent event) {
        event.getDispatcher().register(Commands.literal("deusex")
                .then(Commands.literal("start")
                        .then(Commands.argument("player", EntityArgument.player())
                                .then(Commands.argument("hp", IntegerArgumentType.integer(1, 100))
                                        .executes(ctx -> ShowOrchestrator.commandStart(
                                                EntityArgument.getPlayer(ctx, "player"),
                                                IntegerArgumentType.getInteger(ctx, "hp"))))))
                .then(Commands.literal("reset")
                        .executes(ctx -> ShowOrchestrator.commandReset()))
                .then(Commands.literal("phase2")
                        .requires(source -> source.hasPermission(2))
                        .executes(ctx -> ShowOrchestrator.commandPhase2(ctx.getSource()))));
    }
}
