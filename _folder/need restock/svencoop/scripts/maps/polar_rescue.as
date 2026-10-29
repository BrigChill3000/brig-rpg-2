/**
 * Polar Rescue
 *
 * Stolen and re-factored by Adam "Adambean" Reece from Hezus' "SND" map
 * Based on original work by Hezus
 * Based on original work by Tomas "GeckoN" Slavotinek
 */

#include "point_checkpoint"



/**
 * Map initialisation handler.
 * @return void
 */
void MapInit()
{
    RegisterPointCheckPointEntity();
    PolarRescue::Init();

    g_SurvivalMode.EnableMapSupport();
}

/**
 * Map hook: Activate survival mode.
 * @return void
 */
void ActivateSurvival(CBaseEntity@ pActivator, CBaseEntity@ pCaller, USE_TYPE useType, float flValue)
{
    g_SurvivalMode.Activate();
}

/**
 * Map hook: Start game.
 * @return void
 */
void StartGame(CBaseEntity@ pActivator, CBaseEntity@ pCaller, USE_TYPE useType, float flValue)
{
    PolarRescue::StartGame();
}

/**
 * Map hook: Update objectives.
 * @return void
 */
void UpdateObjectives(CBaseEntity@ pActivator, CBaseEntity@ pCaller, USE_TYPE useType, float flValue)
{
    PolarRescue::UpdateObjectives();
}

/**
 * Map hook: Send objective.
 * @return void
 */
void SendObjective(CBaseEntity@ pActivator, CBaseEntity@ pCaller, USE_TYPE useType, float flValue)
{
    if (pActivator !is null and pActivator.IsPlayer()) {
        PolarRescue::SendObjective(cast<CBasePlayer@>(pActivator), int(flValue));
    }
}



namespace PolarRescue
{
    const int OBJECTIVE_COUNT = 5;
    enum g_eObjectives
    {
        eHostageSecure      = 1,
        eDisarmWarheads     = 2,
        eCollectDocuments   = 3,
        eClearLandingZone   = 4,
        eHostageRefuge      = 5,
    };

    const string        ENT_OBJECTIVE_STATUS    = "objectives_status";  // must be info_target
    EHandle             g_hObjectiveStatus;
    const string        ENT_OBJECTIVE_COUNTER   = "objectives_counter"; // must be game_counter
    EHandle             g_hObjectiveCounter;
    const array<string> ENT_OBVECTIVE_KEYS      = {
        "hostage_secure",
        "disarm_warheads",
        "collect_documents",
        "clear_landing_zone",
        "hostage_refuge",
    };

    array<bool>         g_fShowObjective(OBJECTIVE_COUNT, false);
    array<int>          g_iObjective(OBJECTIVE_COUNT, -1);
    array<int>          g_iObjectiveLastSent(OBJECTIVE_COUNT, -1);

    /**
     * Initialise HUD.
     * @return void
     */
    void Init()
    {
        g_Hooks.RegisterHook(Hooks::Player::ClientPutInServer, @ClientPutInServer);

        for (int i = 0; i < OBJECTIVE_COUNT; i++) {
            int iObjective = (i + 1);

            g_fShowObjective[i] = false;
            g_iObjective[i]     = 0;

            string szSprite;
            snprintf(szSprite, "sprites/adamr/polar_rescue/objective%1.spr", iObjective);
            g_Game.PrecacheModel(szSprite);
        }
    }

    /**
     * Player join handler.
     * @param  CBasePlayer@   pPlayer Player
     * @return HookReturnCode
     */
    HookReturnCode ClientPutInServer(CBasePlayer@ pPlayer)
    {
        for (int i = 0; i < OBJECTIVE_COUNT; i++) {
            int iObjective = (i + 1);

            SendObjective(pPlayer, iObjective);
        }

        return HOOK_CONTINUE;
    }

    /**
     * Start the game.
     * @return void
     */
    void StartGame()
    {
        CBaseEntity @pEntity;

        // Get status entity
        if ((@pEntity = g_EntityFuncs.FindEntityByTargetname(null, ENT_OBJECTIVE_STATUS)) is null) {
            g_Game.AlertMessage(at_error, "Objectives status entity \"%1\" not found.\n", ENT_OBJECTIVE_STATUS);
            return;
        }

        if (pEntity.pev.classname != "info_target") {
            g_Game.AlertMessage(at_error, "Objectives status entity \"%1\" invalid. (Should be \"info_target\", actually a \"%2\".)\n", ENT_OBJECTIVE_STATUS, pEntity.pev.classname);
            return;
        }

        g_hObjectiveStatus = EHandle(pEntity);

        // Get counter entity
        if ((@pEntity = g_EntityFuncs.FindEntityByTargetname(null, ENT_OBJECTIVE_COUNTER)) is null) {
            g_Game.AlertMessage(at_error, "Objectives counter entity \"%1\" not found.\n", ENT_OBJECTIVE_COUNTER);
            return;
        }

        if (pEntity.pev.classname != "game_counter") {
            g_Game.AlertMessage(at_error, "Objectives counter entity \"%1\" invalid. (Should be \"game_counter\", actually a \"%2\".)\n", ENT_OBJECTIVE_COUNTER, pEntity.pev.classname);
            return;
        }

        g_hObjectiveCounter = EHandle(pEntity);

        // Set-up schedule
        g_Scheduler.SetInterval("PeriodicUpdateObjectives", 0.5f, g_Scheduler.REPEAT_INFINITE_TIMES);
    }

    /**
     * Convert an RGB string into a structure.
     * @param  string szColour Colour as RGBA string
     * @return RGBA            Colour as RGBA structure
     */
    RGBA StringToRGBA(const string& in szColour)
    {
        RGBA sColour = RGBA_WHITE;
        array<string>@ strComp = szColour.Split(" ");

        if (strComp.length() == 4) {
            sColour.r = atoi(strComp[0]);
            sColour.g = atoi(strComp[1]);
            sColour.b = atoi(strComp[2]);
            sColour.a = atoi(strComp[3]);
        }

        return sColour;
    }

    /**
     * Create a message.
     * @param  CBasePlayer@ pPlayer Player entity, or null for all players
     * @param  string       szText  Message
     * @param  float        flX     X position as a 0-1 percentage (-1 for centre)
     * @param  float        flY     Y position as a 0-1 percentage (-1 for centre)
     * @param  RGBA         sColour Colour
     * @param  float        flIn    Fade in time
     * @param  float        flOut   Fade out time
     * @param  float        flHold  Hold time
     * @return void
     */
    void Message(CBasePlayer@ pPlayer, const string& in szText, float flX = -1, float flY = -1, RGBA sColour = RGBA_WHITE, float flIn = 0.5, float flOut = 0.5, float flHold = 5.0)
    {
        HUDTextParams sHudText;

        sHudText.x              = flX;
        sHudText.y              = flX;
        sHudText.effect         = 0;

        sHudText.r1             = sHudText.r2 = sColour.r;
        sHudText.g1             = sHudText.g2 = sColour.g;
        sHudText.b1             = sHudText.b2 = sColour.b;
        sHudText.a1             = sHudText.a2 = sColour.a;

        sHudText.fadeinTime     = flIn;
        sHudText.fadeoutTime    = flOut;
        sHudText.holdTime       = flHold;
        sHudText.fxTime         = 0;//0.25f;
        sHudText.channel        = 1;

        if (pPlayer !is null) {
            g_PlayerFuncs.HudMessage(pPlayer, sHudText, szText);
        } else {
            g_PlayerFuncs.HudMessageAll(sHudText, szText);
        }
    }

    /**
     * Update objectives.
     * @param  int|null iObjective Objective number, or 0 for all
     * @return void
     */
    void UpdateObjectives(int iObjective = 0)
    {
        if (iObjective < 0 || iObjective > OBJECTIVE_COUNT) {
            g_Game.AlertMessage(at_error, "PolarRescue::UpdateObjectives(): Objective %1 out of bounds.\n", iObjective);
            return;
        }

        if (!g_hObjectiveCounter.IsValid()) {
            g_Game.AlertMessage(at_error, "PolarRescue::UpdateObjectives(): Objectives counter not defined.\n");
            return;
        }

        CBaseEntity@ pObjectiveCounter = g_hObjectiveCounter.GetEntity();
        if (pObjectiveCounter.pev.frags >= pObjectiveCounter.pev.health) {
            return;
        }

        if (iObjective >= 1) {
            UpdateObjective(iObjective);
        } else {
            g_Game.AlertMessage(at_aiconsole, "PolarRescue::UpdateObjectives(): Updating all objectives...\n");
            for (int i = 0; i < OBJECTIVE_COUNT; i++) {
                UpdateObjective(i + 1);
            }
        }

        pObjectiveCounter.pev.frags = 0;
        for (int i = 0; i < OBJECTIVE_COUNT; i++) {
            if (g_iObjective[i] >= 1) {
                pObjectiveCounter.Use(pObjectiveCounter, pObjectiveCounter, USE_ON);
            }
        }
        g_Game.AlertMessage(at_aiconsole, "PolarRescue::UpdateObjectives(): %1/%2 objectives completed.\n", pObjectiveCounter.pev.frags, pObjectiveCounter.pev.health);

        if (pObjectiveCounter.pev.frags >= pObjectiveCounter.pev.health) {
            g_Game.AlertMessage(at_aiconsole, "PolarRescue::UpdateObjectives(): All objectives completed.\n");
        }
    }

    /**
     * Update objective.
     * @param  int  iObjective Objective number
     * @return void
     */
    void UpdateObjective(int iObjective)
    {
        if (iObjective < 1 || iObjective > OBJECTIVE_COUNT) {
            g_Game.AlertMessage(at_error, "PolarRescue::UpdateObjective(): Objective %1 out of bounds.\n", iObjective);
            return;
        }

        if (!g_hObjectiveStatus.IsValid()) {
            g_Game.AlertMessage(at_error, "PolarRescue::UpdateObjective(): Objectives status not defined.\n");
            return;
        }

        CBaseEntity@        pObjectiveStatus        = g_hObjectiveStatus.GetEntity();
        CustomKeyvalues@    pObjectiveStatusExtra   = pObjectiveStatus.GetCustomKeyvalues();

        int i = (iObjective - 1);
        string szObjectiveKey;
        snprintf(szObjectiveKey, "$i_%1", ENT_OBVECTIVE_KEYS[i]);

        g_Game.AlertMessage(at_aiconsole, "PolarRescue::UpdateObjective(): Updating objective %1 (%2)...\n", iObjective, ENT_OBVECTIVE_KEYS[i]);
        if (pObjectiveStatusExtra.HasKeyvalue(szObjectiveKey) and pObjectiveStatusExtra.GetKeyvalue(szObjectiveKey).Exists()) {
            g_iObjective[i] = pObjectiveStatusExtra.GetKeyvalue(szObjectiveKey).GetInteger();
            g_Game.AlertMessage(at_aiconsole, "PolarRescue::UpdateObjective(): Objective %1 (%2) is %3.\n", iObjective, ENT_OBVECTIVE_KEYS[i], g_iObjective[i]);
        } else {
            g_Game.AlertMessage(at_warning, "PolarRescue::UpdateObjective(): Objective %1 (%2) key not found in objectives status.\n", iObjective, ENT_OBVECTIVE_KEYS[i]);
        }
    }

    /**
     * Periodically update objectives.
     * @return void
     */
    void PeriodicUpdateObjectives()
    {
        if (g_hObjectiveCounter.IsValid()) {
            g_Game.AlertMessage(at_aiconsole, "PolarRescue::PeriodicUpdateObjectives(): Updating objectives...\n");
            UpdateObjectives();
        }

        g_Game.AlertMessage(at_aiconsole, "PolarRescue::PeriodicUpdateObjectives(): Sending objectives...\n");
        for (int i = 0; i < OBJECTIVE_COUNT; i++) {
            int iObjective = (i + 1);

            if (g_fShowObjective[i]) {
                if (g_iObjectiveLastSent[i] != g_iObjective[i]) {
                    g_Game.AlertMessage(at_aiconsole, "PolarRescue::PeriodicUpdateObjectives(): Objective %1 (%2) changed (was %3 now %4), sending.\n", iObjective, ENT_OBVECTIVE_KEYS[i], g_iObjectiveLastSent[i], g_iObjective[i]);
                    SendObjective(null, iObjective);
                    g_iObjectiveLastSent[i] = g_iObjective[i];
                }
            }
        }
    }

    /**
     * Send objective state to player.
     * @param  CBasePlayer@ pPlayer    Player
     * @param  int          iObjective Objective number
     * @return void
     */
    void SendObjective(CBasePlayer@ pPlayer, int iObjective)
    {
        if (iObjective < 1 || iObjective > OBJECTIVE_COUNT) {
            g_Game.AlertMessage(at_error, "PolarRescue::SendObjective(): Objective %1 out of bounds.\n", iObjective);
            return;
        }

        int i = (iObjective - 1);

        g_fShowObjective[i] = true;

        HUDSpriteParams sHudSprite;

        sHudSprite.channel      = iObjective;
        sHudSprite.flags        = HUD_ELEM_SCR_CENTER_X | HUD_ELEM_DEFAULT_ALPHA;
        sHudSprite.x            = 1;
        sHudSprite.y            = 0.3 + (i * 0.1);
        sHudSprite.spritename   = "";
        snprintf(sHudSprite.spritename, "adamr/polar_rescue/objective%1.spr", (i + 1));

        switch (g_iObjective[i]) {
            case -1:
                sHudSprite.color1 = RGBA_WHITE;
                break;

            case 0:
                sHudSprite.color1 = RGBA_RED;
                break;

            case 1:
                sHudSprite.color1 = RGBA_SVENCOOP;
                break;

            default:
                sHudSprite.color1 = RGBA_BLACK;
        }

        if (pPlayer is null) {
            g_Game.AlertMessage(at_aiconsole, "PolarRescue::SendObjective(): Sending objective %1 (%2) in state %3 to all players.\n", iObjective, ENT_OBVECTIVE_KEYS[i], g_iObjective[i]);

            for (int p = 1; p <= g_Engine.maxClients; p++) {
                g_Game.AlertMessage(at_aiconsole, "PolarRescue::SendObjective(): Sending objective %1 (%2) in state %3 to player #%4.\n", iObjective, ENT_OBVECTIVE_KEYS[i], g_iObjective[i], p);

                @pPlayer = g_PlayerFuncs.FindPlayerByIndex(p);
                if (pPlayer is null or !pPlayer.IsPlayer() or !pPlayer.IsConnected()) {
                    g_Game.AlertMessage(at_aiconsole, "PolarRescue::SendObjective(): Player #%1 invalid, not a player, or not connected. Skipping.\n", p);
                    continue;
                }

                g_PlayerFuncs.HudCustomSprite(pPlayer, sHudSprite);
            }
        } else {
            int p = pPlayer.entindex();
            g_Game.AlertMessage(at_aiconsole, "PolarRescue::SendObjective(): Sending objective %1 (%2) in state %3 to player #%4.\n", iObjective, ENT_OBVECTIVE_KEYS[i], g_iObjective[i], p);

            if (!pPlayer.IsPlayer() or !pPlayer.IsConnected()) {
                g_Game.AlertMessage(at_aiconsole, "PolarRescue::SendObjective(): Player #%1 invalid, not a player, or not connected. Skipping.\n", p);
                return;
            }

            g_PlayerFuncs.HudCustomSprite(pPlayer, sHudSprite);
        }
    }

    /**
     * Toggle objective display.
     * @param  int  iObjective Objective number
     * @param  bool fVisible   Visible or not
     * @return void
     */
    void ToggleObjectiveDisplay(int iObjective, bool fVisible)
    {
        if (iObjective < 1 || iObjective > OBJECTIVE_COUNT) {
            g_Game.AlertMessage(at_error, "PolarRescue::ToggleObjectiveDisplay(): Objective %1 out of bounds.\n", iObjective);
            return;
        }

        int i = (iObjective - 1);

        g_fShowObjective[i] = fVisible;

        if (g_fShowObjective[i]) {
            SendObjective(null, i);
        } else {
            g_PlayerFuncs.HudToggleElement(null, iObjective, false);
        }
    }
}
