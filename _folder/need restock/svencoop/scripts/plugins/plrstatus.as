HUDTextParams g_HudParams;

void PluginInit()
{
    g_Module.ScriptInfo.SetAuthor(".");
    g_Module.ScriptInfo.SetContactInfo(".");

    SetupHudParams();
    g_Scheduler.SetInterval("DisplayPlayersState", 0.3f, -1);
}

void SetupHudParams()
{
    g_HudParams.x = 0.75f;
    g_HudParams.y = 0.02f;
    g_HudParams.channel = 4; 
    g_HudParams.effect = 0;
    g_HudParams.a1 = 0;
    g_HudParams.fadeinTime = 0.0f;
    g_HudParams.fadeoutTime = 0.0f;
    g_HudParams.holdTime = 1.0f;
    g_HudParams.fxTime = 0.0f;
}	
void DisplayPlayersState()
{
    for (int i = 1; i <= g_Engine.maxClients; i++)
    {
        CBasePlayer@ pViewer = g_PlayerFuncs.FindPlayerByIndex(i);
        if (pViewer is null || !pViewer.IsConnected())
            continue;

        float yOffset = 0.02f;
        int channel = 4;

        for (int j = 1; j <= g_Engine.maxClients; j++)
        {
            CBasePlayer@ pTarget = g_PlayerFuncs.FindPlayerByIndex(j);
            if (pTarget !is null && pTarget.IsConnected())
            {
				string stateStr;
				int hp = int(pTarget.pev.health);

				if (pTarget.pev.iuser1 != 0)
				{
					stateStr = "OBSERVER";
					g_HudParams.r1 = 128;
					g_HudParams.g1 = 128;
					g_HudParams.b1 = 255;
				}
				else if (!pTarget.IsAlive())
				{
					stateStr = "DEAD";
					g_HudParams.r1 = 150;
					g_HudParams.g1 = 150;
					g_HudParams.b1 = 150;
				}
				else
				{
						stateStr = formatInt(hp) + " HP";

					if (hp <= 25)
					{
						g_HudParams.r1 = 255;
						g_HudParams.g1 = 0;
						g_HudParams.b1 = 0;
					}
					else if (hp <= 75)
					{
						g_HudParams.r1 = 255;
						g_HudParams.g1 = 255;
						g_HudParams.b1 = 0;
					}
					else
					{
						g_HudParams.r1 = 0;
						g_HudParams.g1 = 255;
						g_HudParams.b1 = 0;
					}
				}


                g_HudParams.channel = channel;
                g_HudParams.y = yOffset;

                string msg = "> " + pTarget.pev.netname + " - " + stateStr;
                g_PlayerFuncs.HudMessage(pViewer, g_HudParams, msg);

                yOffset += 0.03f;
                channel++;
                if (channel > 6)
                    break;
            }
        }
    }
}
