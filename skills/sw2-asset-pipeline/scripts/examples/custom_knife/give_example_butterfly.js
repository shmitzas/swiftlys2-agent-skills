import { Instance, CSGearSlot, Console } from "cs_script/point_script";

// Map test harness: every player on the map spawns holding the example butterfly knife. Copy it to the content
// addon's maps/scripts/ and point a point_script entity's cs_script at maps/scripts/give_example_butterfly.vjs;
// remove that entity before publishing the map. A model path can't go in game_player_equip, which takes item names.
const MODEL = "weapons/custom/knife/example_butterfly/example_butterfly.vmdl"; // written by build_example_butterfly.py
const BUTTERFLY = "weapon_knife_butterfly";
// On, the knife takes the butterfly subclass (item definition index 515): clients play butterfly animations on the
// stock default knife (seen in game, 2026-11), apparently because they pick the model from the item definition index,
// which map scripts can't set. Whether those animations move this model's blade, rear and lock bones needs a plugin
// that sets the index. Off, clients draw this model on default-knife animations (seen in game, 2026-11), which should
// leave those bones in the bind pose: knife open, latch hanging.
const CONVERT_TO_BUTTERFLY = false;
const CLIENT_LOAD_TIMEOUT = 10; // seconds; a client that never loads must not block the swap forever

const precache = Instance.Precache({ resources: [MODEL] });
if (!precache) Console.Log("[example_butterfly] Precache unavailable, knife model will not be applied");

async function WaitFor(check, seconds) {
    for (let waited = 0; !check() && waited < seconds; waited += 0.05) await Instance.Delay(0.05);
    return check();
}

// Precaution, not a reproduced crash: change the knife's model at a clean point in the tick, not mid-think.
const AfterThinks = () => new Promise(resolve => Instance.QueueAfterThinks(resolve));

async function ArmWithExampleButterfly(pawn) {
    await Instance.Delay(0.1); // let the spawn loadout and any game_player_equip land first
    if (!precache) return;
    await WaitFor(() => precache.IsLoadedForAll(), CLIENT_LOAD_TIMEOUT);
    if (!precache.IsServerLoaded()) return;
    await AfterThinks();
    if (!pawn.IsValid() || !pawn.IsAlive()) return;

    let knife = pawn.FindWeaponBySlot(CSGearSlot.KNIFE);
    if (knife && knife.GetModelName() === MODEL) return;
    const start = knife ? `${knife.GetData().GetName()} (${knife.GetModelName()})` : "no knife";

    // Start from a freshly given weapon_knife; giving a skin knife by name gave nothing for the bayonet, so the
    // subclass comes from ChangeSubclass instead.
    const wasActive = knife !== undefined && pawn.GetActiveWeapon() === knife;
    if (knife) pawn.DestroyWeapon(knife);
    pawn.GiveNamedItem("weapon_knife", wasActive);
    knife = pawn.FindWeaponBySlot(CSGearSlot.KNIFE);
    if (!knife) return Console.Log("[example_butterfly] weapon_knife could not be given");

    if (CONVERT_TO_BUTTERFLY) {
        knife.FireInput({ input: "ChangeSubclass", value: "515" });
        // The subclass change re-applies the stock model, so the swap has to come after it.
        await WaitFor(() => !knife.IsValid() || knife.GetData().GetName() === BUTTERFLY, 1.0);
        await AfterThinks();
        knife = pawn.IsValid() ? pawn.FindWeaponBySlot(CSGearSlot.KNIFE) : undefined;
        if (!knife) return Console.Log("[example_butterfly] knife vanished during ChangeSubclass");
    }
    knife.SetModel(MODEL);

    // Tells a server-side reset (fixed by re-applying) apart from a client drawing its own model.
    await Instance.Delay(1.0);
    if (!knife.IsValid()) return;
    const held = knife.GetModelName();
    if (held !== MODEL) knife.SetModel(MODEL);
    Console.Log(`[example_butterfly] start ${start} -> ${knife.GetData().GetName()}; server model after 1s: ${held}` +
        (held !== MODEL ? " (was reset, re-applied)" : ""));
}

Instance.OnPlayerReset(({ player }) => { ArmWithExampleButterfly(player); });
