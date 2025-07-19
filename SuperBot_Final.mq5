//+------------------------------------------------------------------+
//|                                                SuperBot_Final.mq5 |
//|                                  Copyright 2024, SuperBot Team   |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, SuperBot Team"
#property link      "https://www.mql5.com"
#property version   "1.00"
#property description "SuperBot: Multi-stage trading EA from $1 to $200+"

//--- Input parameters
input group "=== Risk Management ==="
input double InpRiskPercent = 2.0;           // Risk per trade (%)
input int    InpMaxDrawdown = 30;            // Maximum drawdown (%)
input int    InpMaxConsecutiveLosses = 3;    // Max consecutive losses before pause

input group "=== Trading Parameters ==="
input int    InpTakeProfit = 15;             // Take Profit (pips)
input int    InpStopLoss = 10;               // Stop Loss (pips)
input bool   InpUseTrailingStop = true;     // Use trailing stop
input int    InpTrailingDistance = 5;       // Trailing stop distance (pips)

input group "=== Technical Indicators ==="
input int    InpEMAFast = 8;                 // Fast EMA period
input int    InpEMASlow = 21;                // Slow EMA period
input int    InpRSIPeriod = 14;              // RSI period
input int    InpRSIOverbought = 70;          // RSI overbought level
input int    InpRSIOversold = 30;            // RSI oversold level
input int    InpBBPeriod = 20;               // Bollinger Bands period
input double InpBBDeviation = 2.0;           // BB standard deviation

input group "=== Growth Stages ==="
input double InpStage1Target = 20.0;         // Stage 1 target ($1 -> $20)
input double InpStage2Target = 100.0;        // Stage 2 target ($20 -> $100)
input double InpStage3Target = 200.0;        // Stage 3 target ($100 -> $200+)

input group "=== UI Settings ==="
input bool   InpShowPanel = true;            // Show control panel
input int    InpPanelX = 20;                 // Panel X position
input int    InpPanelY = 20;                 // Panel Y position

//--- Global variables
int handleEMAFast = INVALID_HANDLE;
int handleEMASlow = INVALID_HANDLE;
int handleRSI = INVALID_HANDLE;
int handleBB = INVALID_HANDLE;

double emaFastBuffer[];
double emaSlowBuffer[];
double rsiBuffer[];
double bbUpperBuffer[];
double bbLowerBuffer[];
double bbMiddleBuffer[];

double initialBalance;
double peakBalance;
double currentDrawdown;
int consecutiveLosses;
int totalTrades;
int winningTrades;
double winRate;

bool tradingEnabled = true;
bool isInitialized = false;

enum TRADING_STAGE
{
   STAGE_1_SCALPING,    // $1 -> $20 (V75 scalping)
   STAGE_2_SAFER,       // $20 -> $100 (safer pairs)
   STAGE_3_SWING        // $100+ (swing trading)
};

TRADING_STAGE currentStage = STAGE_1_SCALPING;

//--- UI Objects
string panelName = "SuperBotPanel";
string btnStart = "btnStart";
string btnStop = "btnStop";
string lblEquity = "lblEquity";
string lblDrawdown = "lblDrawdown";
string lblWinRate = "lblWinRate";
string lblStage = "lblStage";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("SuperBot EA initializing...");
   
   // Initialize indicators with error checking
   handleEMAFast = iMA(_Symbol, PERIOD_M15, InpEMAFast, 0, MODE_EMA, PRICE_CLOSE);
   if(handleEMAFast == INVALID_HANDLE)
   {
      Print("Error creating Fast EMA indicator");
      return INIT_FAILED;
   }
   
   handleEMASlow = iMA(_Symbol, PERIOD_M15, InpEMASlow, 0, MODE_EMA, PRICE_CLOSE);
   if(handleEMASlow == INVALID_HANDLE)
   {
      Print("Error creating Slow EMA indicator");
      return INIT_FAILED;
   }
   
   handleRSI = iRSI(_Symbol, PERIOD_M15, InpRSIPeriod, PRICE_CLOSE);
   if(handleRSI == INVALID_HANDLE)
   {
      Print("Error creating RSI indicator");
      return INIT_FAILED;
   }
   
   handleBB = iBands(_Symbol, PERIOD_M15, InpBBPeriod, 0, InpBBDeviation, PRICE_CLOSE);
   if(handleBB == INVALID_HANDLE)
   {
      Print("Error creating Bollinger Bands indicator");
      return INIT_FAILED;
   }
   
   // Initialize arrays
   ArraySetAsSeries(emaFastBuffer, true);
   ArraySetAsSeries(emaSlowBuffer, true);
   ArraySetAsSeries(rsiBuffer, true);
   ArraySetAsSeries(bbUpperBuffer, true);
   ArraySetAsSeries(bbLowerBuffer, true);
   ArraySetAsSeries(bbMiddleBuffer, true);
   
   // Initialize trading variables
   initialBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   peakBalance = initialBalance;
   currentDrawdown = 0.0;
   consecutiveLosses = 0;
   totalTrades = 0;
   winningTrades = 0;
   winRate = 0.0;
   
   // Determine current stage based on balance
   DetermineCurrentStage();
   
   // Create UI panel
   if(InpShowPanel)
      CreatePanel();
   
   isInitialized = true;
   Print("SuperBot EA initialized successfully. Current stage: ", (int)currentStage);
   
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Clean up indicators
   if(handleEMAFast != INVALID_HANDLE) 
   {
      IndicatorRelease(handleEMAFast);
      handleEMAFast = INVALID_HANDLE;
   }
   if(handleEMASlow != INVALID_HANDLE) 
   {
      IndicatorRelease(handleEMASlow);
      handleEMASlow = INVALID_HANDLE;
   }
   if(handleRSI != INVALID_HANDLE) 
   {
      IndicatorRelease(handleRSI);
      handleRSI = INVALID_HANDLE;
   }
   if(handleBB != INVALID_HANDLE) 
   {
      IndicatorRelease(handleBB);
      handleBB = INVALID_HANDLE;
   }
   
   // Clean up UI
   if(InpShowPanel)
      DeletePanel();
   
   Print("SuperBot EA deinitialized");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!isInitialized || !tradingEnabled)
      return;
   
   // Update trading statistics
   UpdateTradingStats();
   
   // Check risk management conditions
   if(!CheckRiskManagement())
      return;
   
   // Update UI
   if(InpShowPanel)
      UpdatePanel();
   
   // Check for new trading opportunities
   CheckTradingSignals();
   
   // Manage existing positions
   ManagePositions();
}

//+------------------------------------------------------------------+
//| Check trading signals based on current stage                     |
//+------------------------------------------------------------------+
void CheckTradingSignals()
{
   // Ensure we have enough historical data
   if(!UpdateIndicatorBuffers())
      return;
   
   // Limit to maximum 2 open positions
   if(PositionsTotal() >= 2)
      return;
   
   switch(currentStage)
   {
      case STAGE_1_SCALPING:
         CheckScalpingSignals();
         break;
      case STAGE_2_SAFER:
         CheckSaferSignals();
         break;
      case STAGE_3_SWING:
         CheckSwingSignals();
         break;
   }
}

//+------------------------------------------------------------------+
//| Check scalping signals for Stage 1 (V75)                        |
//+------------------------------------------------------------------+
void CheckScalpingSignals()
{
   // EMA crossover strategy with RSI and BB confirmation
   bool emaBullishCross = (emaFastBuffer[1] <= emaSlowBuffer[1] && emaFastBuffer[0] > emaSlowBuffer[0]);
   bool emaBearishCross = (emaFastBuffer[1] >= emaSlowBuffer[1] && emaFastBuffer[0] < emaSlowBuffer[0]);
   
   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   // Buy signal: EMA bullish cross + RSI oversold recovery + price above BB middle
   if(emaBullishCross && rsiBuffer[0] > InpRSIOversold && rsiBuffer[1] <= InpRSIOversold && 
      currentPrice > bbMiddleBuffer[0])
   {
      OpenPosition(ORDER_TYPE_BUY, "Stage1 Scalp Buy");
   }
   
   // Sell signal: EMA bearish cross + RSI overbought decline + price below BB middle
   if(emaBearishCross && rsiBuffer[0] < InpRSIOverbought && rsiBuffer[1] >= InpRSIOverbought && 
      currentPrice < bbMiddleBuffer[0])
   {
      OpenPosition(ORDER_TYPE_SELL, "Stage1 Scalp Sell");
   }
}

//+------------------------------------------------------------------+
//| Check safer signals for Stage 2                                  |
//+------------------------------------------------------------------+
void CheckSaferSignals()
{
   // More conservative approach with additional confirmation
   bool strongBullish = (emaFastBuffer[0] > emaSlowBuffer[0] && 
                        rsiBuffer[0] > 50 && rsiBuffer[0] < InpRSIOverbought);
   bool strongBearish = (emaFastBuffer[0] < emaSlowBuffer[0] && 
                        rsiBuffer[0] < 50 && rsiBuffer[0] > InpRSIOversold);
   
   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   if(strongBullish && currentPrice > bbMiddleBuffer[0])
   {
      OpenPosition(ORDER_TYPE_BUY, "Stage2 Safer Buy");
   }
   
   if(strongBearish && currentPrice < bbMiddleBuffer[0])
   {
      OpenPosition(ORDER_TYPE_SELL, "Stage2 Safer Sell");
   }
}

//+------------------------------------------------------------------+
//| Check swing signals for Stage 3                                  |
//+------------------------------------------------------------------+
void CheckSwingSignals()
{
   // Swing trading logic - look for strong trends and breakouts
   bool trendUp = (emaFastBuffer[0] > emaSlowBuffer[0] && emaFastBuffer[1] > emaSlowBuffer[1] && 
                  emaFastBuffer[2] > emaSlowBuffer[2]);
   bool trendDown = (emaFastBuffer[0] < emaSlowBuffer[0] && emaFastBuffer[1] < emaSlowBuffer[1] && 
                    emaFastBuffer[2] < emaSlowBuffer[2]);
   
   double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   // Look for pullbacks in strong trends
   if(trendUp && rsiBuffer[0] < 50 && rsiBuffer[1] < rsiBuffer[0] && currentPrice > bbLowerBuffer[0])
   {
      OpenPosition(ORDER_TYPE_BUY, "Stage3 Swing Buy");
   }
   
   if(trendDown && rsiBuffer[0] > 50 && rsiBuffer[1] > rsiBuffer[0] && currentPrice < bbUpperBuffer[0])
   {
      OpenPosition(ORDER_TYPE_SELL, "Stage3 Swing Sell");
   }
}

//+------------------------------------------------------------------+
//| Open a new position                                              |
//+------------------------------------------------------------------+
void OpenPosition(ENUM_ORDER_TYPE orderType, string comment)
{
   double lotSize = CalculateLotSize();
   if(lotSize <= 0)
      return;
   
   double price, sl, tp;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   
   if(orderType == ORDER_TYPE_BUY)
   {
      price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      sl = NormalizeDouble(price - InpStopLoss * point * 10, digits);
      tp = NormalizeDouble(price + InpTakeProfit * point * 10, digits);
   }
   else
   {
      price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      sl = NormalizeDouble(price + InpStopLoss * point * 10, digits);
      tp = NormalizeDouble(price - InpTakeProfit * point * 10, digits);
   }
   
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.volume = lotSize;
   request.type = orderType;
   request.price = price;
   request.sl = sl;
   request.tp = tp;
   request.comment = comment;
   request.magic = 12345;
   request.deviation = 3;
   
   if(OrderSend(request, result))
   {
      Print("Position opened: ", comment, " Volume: ", lotSize, " Price: ", price);
   }
   else
   {
      Print("Failed to open position: ", result.comment, " Return code: ", result.retcode);
   }
}

//+------------------------------------------------------------------+
//| Calculate lot size based on risk management                      |
//+------------------------------------------------------------------+
double CalculateLotSize()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = balance * InpRiskPercent / 100.0;
   double stopLossPips = InpStopLoss;
   
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   
   if(tickSize == 0) tickSize = point;
   
   double pointValue = tickValue * point / tickSize;
   double lotSize = riskAmount / (stopLossPips * pointValue * 10);
   
   // Apply lot size limits
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   lotSize = MathMax(lotSize, minLot);
   lotSize = MathMin(lotSize, maxLot);
   
   if(lotStep > 0)
      lotSize = NormalizeDouble(MathRound(lotSize / lotStep) * lotStep, 2);
   
   return lotSize;
}

//+------------------------------------------------------------------+
//| Update indicator buffers                                         |
//+------------------------------------------------------------------+
bool UpdateIndicatorBuffers()
{
   if(CopyBuffer(handleEMAFast, 0, 0, 3, emaFastBuffer) < 3 ||
      CopyBuffer(handleEMASlow, 0, 0, 3, emaSlowBuffer) < 3 ||
      CopyBuffer(handleRSI, 0, 0, 3, rsiBuffer) < 3 ||
      CopyBuffer(handleBB, 1, 0, 3, bbUpperBuffer) < 3 ||
      CopyBuffer(handleBB, 2, 0, 3, bbLowerBuffer) < 3 ||
      CopyBuffer(handleBB, 0, 0, 3, bbMiddleBuffer) < 3)
   {
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Manage existing positions                                        |
//+------------------------------------------------------------------+
void ManagePositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      string posSymbol = PositionGetSymbol(i);
      if(posSymbol == _Symbol)
      {
         if(InpUseTrailingStop)
            ApplyTrailingStop(i);
      }
   }
}

//+------------------------------------------------------------------+
//| Apply trailing stop to position                                  |
//+------------------------------------------------------------------+
void ApplyTrailingStop(int posIndex)
{
   string posSymbol = PositionGetSymbol(posIndex);
   if(posSymbol != _Symbol) return;
   
   ulong ticket = PositionGetTicket(posIndex);
   if(!PositionSelectByTicket(ticket)) return;
   
   double currentPrice;
   double newSL;
   double currentSL = PositionGetDouble(POSITION_SL);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   
   if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
   {
      currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      newSL = NormalizeDouble(currentPrice - InpTrailingDistance * point * 10, digits);
      
      if(newSL > currentSL && currentSL > 0)
      {
         ModifyPosition(ticket, newSL, PositionGetDouble(POSITION_TP));
      }
   }
   else
   {
      currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      newSL = NormalizeDouble(currentPrice + InpTrailingDistance * point * 10, digits);
      
      if((newSL < currentSL && currentSL > 0) || currentSL == 0)
      {
         ModifyPosition(ticket, newSL, PositionGetDouble(POSITION_TP));
      }
   }
}

//+------------------------------------------------------------------+
//| Modify position SL/TP                                           |
//+------------------------------------------------------------------+
void ModifyPosition(ulong ticket, double newSL, double newTP)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_SLTP;
   request.position = ticket;
   request.symbol = _Symbol;
   request.sl = newSL;
   request.tp = newTP;
   
   if(!OrderSend(request, result))
   {
      Print("Failed to modify position: ", result.comment);
   }
}

//+------------------------------------------------------------------+
//| Check risk management conditions                                 |
//+------------------------------------------------------------------+
bool CheckRiskManagement()
{
   // Check maximum drawdown
   if(currentDrawdown > InpMaxDrawdown)
   {
      tradingEnabled = false;
      Print("Trading disabled: Maximum drawdown exceeded (", currentDrawdown, "%)");
      return false;
   }
   
   // Check consecutive losses
   if(consecutiveLosses >= InpMaxConsecutiveLosses)
   {
      tradingEnabled = false;
      Print("Trading disabled: Maximum consecutive losses reached (", consecutiveLosses, ")");
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Update trading statistics                                        |
//+------------------------------------------------------------------+
void UpdateTradingStats()
{
   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   
   // Update peak balance and drawdown
   if(currentBalance > peakBalance)
   {
      peakBalance = currentBalance;
   }
   
   if(peakBalance > 0)
      currentDrawdown = (peakBalance - currentBalance) / peakBalance * 100.0;
   
   // Determine current stage based on balance
   DetermineCurrentStage();
   
   // Calculate win rate (simplified - would need to track individual trades for accuracy)
   if(totalTrades > 0)
   {
      winRate = (double)winningTrades / totalTrades * 100.0;
   }
}

//+------------------------------------------------------------------+
//| Determine current trading stage based on balance                 |
//+------------------------------------------------------------------+
void DetermineCurrentStage()
{
   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   
   if(currentBalance < InpStage1Target)
   {
      currentStage = STAGE_1_SCALPING;
   }
   else if(currentBalance < InpStage2Target)
   {
      currentStage = STAGE_2_SAFER;
   }
   else
   {
      currentStage = STAGE_3_SWING;
   }
}

//+------------------------------------------------------------------+
//| Create UI panel                                                  |
//+------------------------------------------------------------------+
void CreatePanel()
{
   // Main panel
   ObjectCreate(0, panelName, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, panelName, OBJPROP_XDISTANCE, InpPanelX);
   ObjectSetInteger(0, panelName, OBJPROP_YDISTANCE, InpPanelY);
   ObjectSetInteger(0, panelName, OBJPROP_XSIZE, 250);
   ObjectSetInteger(0, panelName, OBJPROP_YSIZE, 200);
   ObjectSetInteger(0, panelName, OBJPROP_BGCOLOR, clrDarkSlateGray);
   ObjectSetInteger(0, panelName, OBJPROP_BORDER_COLOR, clrWhite);
   ObjectSetInteger(0, panelName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   
   // Start button
   ObjectCreate(0, btnStart, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, btnStart, OBJPROP_XDISTANCE, InpPanelX + 10);
   ObjectSetInteger(0, btnStart, OBJPROP_YDISTANCE, InpPanelY + 10);
   ObjectSetInteger(0, btnStart, OBJPROP_XSIZE, 60);
   ObjectSetInteger(0, btnStart, OBJPROP_YSIZE, 25);
   ObjectSetString(0, btnStart, OBJPROP_TEXT, "START");
   ObjectSetInteger(0, btnStart, OBJPROP_COLOR, clrWhite);
   ObjectSetInteger(0, btnStart, OBJPROP_BGCOLOR, clrGreen);
   
   // Stop button
   ObjectCreate(0, btnStop, OBJ_BUTTON, 0, 0, 0);
   ObjectSetInteger(0, btnStop, OBJPROP_XDISTANCE, InpPanelX + 80);
   ObjectSetInteger(0, btnStop, OBJPROP_YDISTANCE, InpPanelY + 10);
   ObjectSetInteger(0, btnStop, OBJPROP_XSIZE, 60);
   ObjectSetInteger(0, btnStop, OBJPROP_YSIZE, 25);
   ObjectSetString(0, btnStop, OBJPROP_TEXT, "STOP");
   ObjectSetInteger(0, btnStop, OBJPROP_COLOR, clrWhite);
   ObjectSetInteger(0, btnStop, OBJPROP_BGCOLOR, clrRed);
   
   // Labels
   CreateLabel(lblEquity, InpPanelX + 10, InpPanelY + 45, "Equity: $0.00");
   CreateLabel(lblDrawdown, InpPanelX + 10, InpPanelY + 65, "Drawdown: 0.00%");
   CreateLabel(lblWinRate, InpPanelX + 10, InpPanelY + 85, "Win Rate: 0.00%");
   CreateLabel(lblStage, InpPanelX + 10, InpPanelY + 105, "Stage: 1 - Scalping");
}

//+------------------------------------------------------------------+
//| Create a label                                                   |
//+------------------------------------------------------------------+
void CreateLabel(string name, int x, int y, string text)
{
   ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
}

//+------------------------------------------------------------------+
//| Update UI panel                                                  |
//+------------------------------------------------------------------+
void UpdatePanel()
{
   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   
   ObjectSetString(0, lblEquity, OBJPROP_TEXT, "Equity: $" + DoubleToString(currentBalance, 2));
   ObjectSetString(0, lblDrawdown, OBJPROP_TEXT, "Drawdown: " + DoubleToString(currentDrawdown, 2) + "%");
   ObjectSetString(0, lblWinRate, OBJPROP_TEXT, "Win Rate: " + DoubleToString(winRate, 2) + "%");
   
   string stageText = "";
   switch(currentStage)
   {
      case STAGE_1_SCALPING: stageText = "Stage: 1 - Scalping"; break;
      case STAGE_2_SAFER: stageText = "Stage: 2 - Safer"; break;
      case STAGE_3_SWING: stageText = "Stage: 3 - Swing"; break;
   }
   ObjectSetString(0, lblStage, OBJPROP_TEXT, stageText);
}

//+------------------------------------------------------------------+
//| Delete UI panel                                                  |
//+------------------------------------------------------------------+
void DeletePanel()
{
   ObjectDelete(0, panelName);
   ObjectDelete(0, btnStart);
   ObjectDelete(0, btnStop);
   ObjectDelete(0, lblEquity);
   ObjectDelete(0, lblDrawdown);
   ObjectDelete(0, lblWinRate);
   ObjectDelete(0, lblStage);
}

//+------------------------------------------------------------------+
//| Chart event handler                                              |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK)
   {
      if(sparam == btnStart)
      {
         tradingEnabled = true;
         consecutiveLosses = 0;
         Print("Trading enabled by user");
         ObjectSetInteger(0, btnStart, OBJPROP_STATE, false);
      }
      else if(sparam == btnStop)
      {
         tradingEnabled = false;
         Print("Trading disabled by user");
         ObjectSetInteger(0, btnStop, OBJPROP_STATE, false);
      }
   }
}

//+------------------------------------------------------------------+
//| Trade event handler                                              |
//+------------------------------------------------------------------+
void OnTrade()
{
   // Update trade statistics when positions are closed
   totalTrades++;
   
   // This is a simplified approach - in a real implementation,
   // you'd track individual trade results more precisely
   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   if(currentBalance > peakBalance)
   {
      winningTrades++;
      consecutiveLosses = 0;
   }
   else
   {
      consecutiveLosses++;
   }
}