HUDTextParams g_HudParams;

float g_flLastFrameTime = 0.0;
float g_flLastHUDUpdate = 0.0;
float g_flCurrentFPS = 0.0;

bool g_bIntervalSet = false;

void PluginInit()
{
    g_Module.ScriptInfo.SetAuthor(".");
    g_Module.ScriptInfo.SetContactInfo(".");
}

void MapInit()
{
    SetupHudParams();
    StartFPSUpdater();
}

void SetupHudParams()
{
    g_HudParams.x = 0.9f;
    g_HudParams.y = 0.9f;

    g_HudParams.r1 = 255;
    g_HudParams.g1 = 255;
    g_HudParams.b1 = 0;
    g_HudParams.a1 = 255;

    g_HudParams.fadeinTime = 0.0f;
    g_HudParams.fadeoutTime = 0.0f;
    g_HudParams.holdTime = 1.0f;
    g_HudParams.channel = 7;
}

void StartFPSUpdater()
{
    if (!g_bIntervalSet)
    {
        g_Scheduler.SetInterval("TickFPS", 0.001, -1);
        g_bIntervalSet = true;
    }
    g_flLastFrameTime = g_Engine.time; 
    g_flLastHUDUpdate = 0.0;
}

void TickFPS()
{
    float currentTime = g_Engine.time;
    float delta = currentTime - g_flLastFrameTime;
    if (delta > 0.0f)
        g_flCurrentFPS = 1.0f / delta;
    g_flLastFrameTime = currentTime;

    if (currentTime - g_flLastHUDUpdate >= 0.5f)
    {
        string text = "Tickrate: " + formatFloat(g_flCurrentFPS, "0.0");

        for (int i = 1; i <= g_Engine.maxClients; i++)
        {
            CBasePlayer@ p = g_PlayerFuncs.FindPlayerByIndex(i);
            if (p !is null && p.IsConnected())
            {
                g_PlayerFuncs.HudMessage(p, g_HudParams, text);
            }
        }
        g_flLastHUDUpdate = currentTime;
    }
}