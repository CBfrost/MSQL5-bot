//+------------------------------------------------------------------+
//|                                            SuperBot_MultiPair.mq5 |
//|                                  Copyright 2024, SuperBot Team   |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, SuperBot Team"
#property link      "https://www.mql5.com"
#property version   "1.10"
#property description "SuperBot: Multi-pair trading EA from $1 to $200+"

//--- Input parameters
input group "=== Symbol Selection ==="
input bool   InpAutoSymbolSelection = true;  // Auto-select best symbols
input string InpStage1Symbols = "EURUSD,GBPUSD,USDJPY,AUDUSD"; // Stage 1 symbols (comma separated)
input string InpStage2Symbols = "EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,NZDUSD"; // Stage 2 symbols
input string InpStage3Symbols = "EURUSD,GBPUSD,USDJPY,XAUUSD,USDCAD,EURGBP"; // Stage 3 symbols

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
struct SymbolInfo
{
   string symbol;
   double spread;
   double volatility;
   bool available;
   int handleEMAFast;
   int handleEMASlow;
   int handleRSI;
   int handleBB;
};

SymbolInfo availableSymbols[];
string activeSymbol;
int activeSymbolIndex;

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
datetime lastSymbolCheck = 0;

enum TRADING_STAGE
{
   STAGE_1_SCALPING,    // $1 -> $20 (High frequency pairs)
   STAGE_2_SAFER,       // $20 -> $100 (Major pairs)
   STAGE_3_SWING        // $100+ (Major + Gold)
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
string lblSymbol = "lblSymbol";
string lblSpread = "lblSpread";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("SuperBot MultiPair EA initializing...");
   
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
   
   // Initialize available symbols
   if(!InitializeSymbols())
   {
      Print("Error: No suitable symbols found");
      return INIT_FAILED;
   }
   
   // Select best symbol for current stage
   SelectBestSymbol();
   
   // Initialize indicators for active symbol
   if(!InitializeIndicators())
   {
      Print("Error: Failed to initialize indicators");
      return INIT_FAILED;
   }
   
   // Initialize arrays
   ArraySetAsSeries(emaFastBuffer, true);
   ArraySetAsSeries(emaSlowBuffer, true);
   ArraySetAsSeries(rsiBuffer, true);
   ArraySetAsSeries(bbUpperBuffer, true);
   ArraySetAsSeries(bbLowerBuffer, true);
   ArraySetAsSeries(bbMiddleBuffer, true);
   
   // Create UI panel
   if(InpShowPanel)
      CreatePanel();
   
   isInitialized = true;
   Print("SuperBot MultiPair EA initialized successfully.");
   Print("Active Symbol: ", activeSymbol, " | Stage: ", (int)currentStage);
   
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Clean up all indicators
   for(int i = 0; i < ArraySize(availableSymbols); i++)
   {
      if(availableSymbols[i].handleEMAFast != INVALID_HANDLE)
         IndicatorRelease(availableSymbols[i].handleEMAFast);
      if(availableSymbols[i].handleEMASlow != INVALID_HANDLE)
         IndicatorRelease(availableSymbols[i].handleEMASlow);
      if(availableSymbols[i].handleRSI != INVALID_HANDLE)
         IndicatorRelease(availableSymbols[i].handleRSI);
      if(availableSymbols[i].handleBB != INVALID_HANDLE)
         IndicatorRelease(availableSymbols[i].handleBB);
   }
   
   // Clean up UI
   if(InpShowPanel)
      DeletePanel();
   
   Print("SuperBot MultiPair EA deinitialized");
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
   
   // Check if we need to switch symbols (every 1 hour)
   if(TimeCurrent() - lastSymbolCheck > 3600)
   {
      CheckSymbolSwitch();
      lastSymbolCheck = TimeCurrent();
   }
   
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
//| Initialize available symbols                                     |
//+------------------------------------------------------------------+
bool InitializeSymbols()
{
   string stageSymbols = "";
   
   // Get symbols for current stage
   switch(currentStage)
   {
      case STAGE_1_SCALPING: stageSymbols = InpStage1Symbols; break;
      case STAGE_2_SAFER: stageSymbols = InpStage2Symbols; break;
      case STAGE_3_SWING: stageSymbols = InpStage3Symbols; break;
   }
   
   // Parse comma-separated symbols
   string symbols[];
   int count = StringSplit(stageSymbols, ',', symbols);
   
   // Clear previous symbols
   ArrayResize(availableSymbols, 0);
   
   // Check each symbol availability
   for(int i = 0; i < count; i++)
   {
      StringTrimLeft(symbols[i]);
      StringTrimRight(symbols[i]);
      
      if(SymbolSelect(symbols[i], true))
      {
         SymbolInfo newSymbol;
         newSymbol.symbol = symbols[i];
         newSymbol.available = true;
         newSymbol.spread = SymbolInfoInteger(symbols[i], SYMBOL_SPREAD);
         newSymbol.volatility = CalculateVolatility(symbols[i]);
         newSymbol.handleEMAFast = INVALID_HANDLE;
         newSymbol.handleEMASlow = INVALID_HANDLE;
         newSymbol.handleRSI = INVALID_HANDLE;
         newSymbol.handleBB = INVALID_HANDLE;
         
         int size = ArraySize(availableSymbols);
         ArrayResize(availableSymbols, size + 1);
         availableSymbols[size] = newSymbol;
         
         Print("Added symbol: ", symbols[i], " | Spread: ", newSymbol.spread, " | Volatility: ", newSymbol.volatility);
      }
      else
      {
         Print("Symbol not available: ", symbols[i]);
      }
   }
   
   return ArraySize(availableSymbols) > 0;
}

//+------------------------------------------------------------------+
//| Calculate symbol volatility                                      |
//+------------------------------------------------------------------+
double CalculateVolatility(string symbol)
{
   double high[], low[];
   if(CopyHigh(symbol, PERIOD_H1, 0, 24, high) < 24 || 
      CopyLow(symbol, PERIOD_H1, 0, 24, low) < 24)
      return 0.0;
   
   double totalRange = 0.0;
   for(int i = 0; i < 24; i++)
   {
      totalRange += (high[i] - low[i]);
   }
   
   return totalRange / 24.0;
}

//+------------------------------------------------------------------+
//| Select best symbol for current conditions                        |
//+------------------------------------------------------------------+
void SelectBestSymbol()
{
   if(ArraySize(availableSymbols) == 0) return;
   
   int bestIndex = 0;
   double bestScore = -1;
   
   for(int i = 0; i < ArraySize(availableSymbols); i++)
   {
      if(!availableSymbols[i].available) continue;
      
      double score = 0;
      
      // Score based on spread (lower is better)
      if(availableSymbols[i].spread > 0)
         score += 100.0 / availableSymbols[i].spread;
      
      // Score based on volatility (higher is better for scalping, moderate for others)
      if(currentStage == STAGE_1_SCALPING)
         score += availableSymbols[i].volatility * 10000;
      else
         score += (1.0 / (availableSymbols[i].volatility * 10000 + 1)) * 50;
      
      // Prefer major pairs
      if(StringFind(availableSymbols[i].symbol, "EUR") >= 0 || 
         StringFind(availableSymbols[i].symbol, "USD") >= 0 ||
         StringFind(availableSymbols[i].symbol, "GBP") >= 0 ||
         StringFind(availableSymbols[i].symbol, "JPY") >= 0)
         score += 20;
      
      // Special preference for gold in stage 3
      if(currentStage == STAGE_3_SWING && StringFind(availableSymbols[i].symbol, "XAU") >= 0)
         score += 30;
      
      if(score > bestScore)
      {
         bestScore = score;
         bestIndex = i;
      }
   }
   
   activeSymbol = availableSymbols[bestIndex].symbol;
   activeSymbolIndex = bestIndex;
   
   Print("Selected symbol: ", activeSymbol, " with score: ", bestScore);
}

//+------------------------------------------------------------------+
//| Initialize indicators for active symbol                          |
//+------------------------------------------------------------------+
bool InitializeIndicators()
{
   if(activeSymbolIndex < 0 || activeSymbolIndex >= ArraySize(availableSymbols))
      return false;
   
   // Release old handles if they exist
   if(availableSymbols[activeSymbolIndex].handleEMAFast != INVALID_HANDLE)
      IndicatorRelease(availableSymbols[activeSymbolIndex].handleEMAFast);
   if(availableSymbols[activeSymbolIndex].handleEMASlow != INVALID_HANDLE)
      IndicatorRelease(availableSymbols[activeSymbolIndex].handleEMASlow);
   if(availableSymbols[activeSymbolIndex].handleRSI != INVALID_HANDLE)
      IndicatorRelease(availableSymbols[activeSymbolIndex].handleRSI);
   if(availableSymbols[activeSymbolIndex].handleBB != INVALID_HANDLE)
      IndicatorRelease(availableSymbols[activeSymbolIndex].handleBB);
   
   // Create new indicators
   availableSymbols[activeSymbolIndex].handleEMAFast = iMA(activeSymbol, PERIOD_M15, InpEMAFast, 0, MODE_EMA, PRICE_CLOSE);
   availableSymbols[activeSymbolIndex].handleEMASlow = iMA(activeSymbol, PERIOD_M15, InpEMASlow, 0, MODE_EMA, PRICE_CLOSE);
   availableSymbols[activeSymbolIndex].handleRSI = iRSI(activeSymbol, PERIOD_M15, InpRSIPeriod, PRICE_CLOSE);
   availableSymbols[activeSymbolIndex].handleBB = iBands(activeSymbol, PERIOD_M15, InpBBPeriod, 0, InpBBDeviation, PRICE_CLOSE);
   
   return (availableSymbols[activeSymbolIndex].handleEMAFast != INVALID_HANDLE &&
           availableSymbols[activeSymbolIndex].handleEMASlow != INVALID_HANDLE &&
           availableSymbols[activeSymbolIndex].handleRSI != INVALID_HANDLE &&
           availableSymbols[activeSymbolIndex].handleBB != INVALID_HANDLE);
}

//+------------------------------------------------------------------+
//| Check if we should switch symbols                                |
//+------------------------------------------------------------------+
void CheckSymbolSwitch()
{
   TRADING_STAGE newStage = currentStage;
   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   
   // Determine if stage changed
   if(currentBalance < InpStage1Target)
      newStage = STAGE_1_SCALPING;
   else if(currentBalance < InpStage2Target)
      newStage = STAGE_2_SAFER;
   else
      newStage = STAGE_3_SWING;
   
   // If stage changed, reinitialize symbols
   if(newStage != currentStage)
   {
      currentStage = newStage;
      Print("Stage changed to: ", (int)currentStage);
      
      // Close all positions before switching
      CloseAllPositions();
      
      // Reinitialize symbols for new stage
      InitializeSymbols();
      SelectBestSymbol();
      InitializeIndicators();
   }
   else
   {
      // Check if current symbol is still optimal
      string previousSymbol = activeSymbol;
      SelectBestSymbol();
      
      if(activeSymbol != previousSymbol)
      {
         Print("Switching from ", previousSymbol, " to ", activeSymbol);
         CloseAllPositions();
         InitializeIndicators();
      }
   }
}

//+------------------------------------------------------------------+
//| Close all open positions                                         |
//+------------------------------------------------------------------+
void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      string posSymbol = PositionGetSymbol(i);
      ulong ticket = PositionGetTicket(i);
      
      MqlTradeRequest request = {};
      MqlTradeResult result = {};
      
      request.action = TRADE_ACTION_DEAL;
      request.position = ticket;
      request.symbol = posSymbol;
      request.volume = PositionGetDouble(POSITION_VOLUME);
      request.type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
      request.price = (request.type == ORDER_TYPE_SELL) ? SymbolInfoDouble(posSymbol, SYMBOL_BID) : SymbolInfoDouble(posSymbol, SYMBOL_ASK);
      request.deviation = 3;
      
      OrderSend(request, result);
   }
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
//| Check scalping signals for Stage 1                              |
//+------------------------------------------------------------------+
void CheckScalpingSignals()
{
   // EMA crossover strategy with RSI and BB confirmation
   bool emaBullishCross = (emaFastBuffer[1] <= emaSlowBuffer[1] && emaFastBuffer[0] > emaSlowBuffer[0]);
   bool emaBearishCross = (emaFastBuffer[1] >= emaSlowBuffer[1] && emaFastBuffer[0] < emaSlowBuffer[0]);
   
   double currentPrice = SymbolInfoDouble(activeSymbol, SYMBOL_BID);
   
   // Buy signal: EMA bullish cross + RSI oversold recovery + price above BB middle
   if(emaBullishCross && rsiBuffer[0] > InpRSIOversold && rsiBuffer[1] <= InpRSIOversold && 
      currentPrice > bbMiddleBuffer[0])
   {
      OpenPosition(ORDER_TYPE_BUY, "Stage1 Scalp Buy - " + activeSymbol);
   }
   
   // Sell signal: EMA bearish cross + RSI overbought decline + price below BB middle
   if(emaBearishCross && rsiBuffer[0] < InpRSIOverbought && rsiBuffer[1] >= InpRSIOverbought && 
      currentPrice < bbMiddleBuffer[0])
   {
      OpenPosition(ORDER_TYPE_SELL, "Stage1 Scalp Sell - " + activeSymbol);
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
   
   double currentPrice = SymbolInfoDouble(activeSymbol, SYMBOL_BID);
   
   if(strongBullish && currentPrice > bbMiddleBuffer[0])
   {
      OpenPosition(ORDER_TYPE_BUY, "Stage2 Safer Buy - " + activeSymbol);
   }
   
   if(strongBearish && currentPrice < bbMiddleBuffer[0])
   {
      OpenPosition(ORDER_TYPE_SELL, "Stage2 Safer Sell - " + activeSymbol);
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
   
   double currentPrice = SymbolInfoDouble(activeSymbol, SYMBOL_BID);
   
   // Look for pullbacks in strong trends
   if(trendUp && rsiBuffer[0] < 50 && rsiBuffer[1] < rsiBuffer[0] && currentPrice > bbLowerBuffer[0])
   {
      OpenPosition(ORDER_TYPE_BUY, "Stage3 Swing Buy - " + activeSymbol);
   }
   
   if(trendDown && rsiBuffer[0] > 50 && rsiBuffer[1] > rsiBuffer[0] && currentPrice < bbUpperBuffer[0])
   {
      OpenPosition(ORDER_TYPE_SELL, "Stage3 Swing Sell - " + activeSymbol);
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
   double point = SymbolInfoDouble(activeSymbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(activeSymbol, SYMBOL_DIGITS);
   
   if(orderType == ORDER_TYPE_BUY)
   {
      price = SymbolInfoDouble(activeSymbol, SYMBOL_ASK);
      sl = NormalizeDouble(price - InpStopLoss * point * 10, digits);
      tp = NormalizeDouble(price + InpTakeProfit * point * 10, digits);
   }
   else
   {
      price = SymbolInfoDouble(activeSymbol, SYMBOL_BID);
      sl = NormalizeDouble(price + InpStopLoss * point * 10, digits);
      tp = NormalizeDouble(price - InpTakeProfit * point * 10, digits);
   }
   
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = activeSymbol;
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
   
   double tickValue = SymbolInfoDouble(activeSymbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(activeSymbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(activeSymbol, SYMBOL_POINT);
   
   if(tickSize == 0) tickSize = point;
   
   double pointValue = tickValue * point / tickSize;
   double lotSize = riskAmount / (stopLossPips * pointValue * 10);
   
   // Apply lot size limits
   double minLot = SymbolInfoDouble(activeSymbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(activeSymbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(activeSymbol, SYMBOL_VOLUME_STEP);
   
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
   if(activeSymbolIndex < 0 || activeSymbolIndex >= ArraySize(availableSymbols))
      return false;
   
   if(CopyBuffer(availableSymbols[activeSymbolIndex].handleEMAFast, 0, 0, 3, emaFastBuffer) < 3 ||
      CopyBuffer(availableSymbols[activeSymbolIndex].handleEMASlow, 0, 0, 3, emaSlowBuffer) < 3 ||
      CopyBuffer(availableSymbols[activeSymbolIndex].handleRSI, 0, 0, 3, rsiBuffer) < 3 ||
      CopyBuffer(availableSymbols[activeSymbolIndex].handleBB, 1, 0, 3, bbUpperBuffer) < 3 ||
      CopyBuffer(availableSymbols[activeSymbolIndex].handleBB, 2, 0, 3, bbLowerBuffer) < 3 ||
      CopyBuffer(availableSymbols[activeSymbolIndex].handleBB, 0, 0, 3, bbMiddleBuffer) < 3)
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
      if(InpUseTrailingStop)
         ApplyTrailingStop(i, posSymbol);
   }
}

//+------------------------------------------------------------------+
//| Apply trailing stop to position                                  |
//+------------------------------------------------------------------+
void ApplyTrailingStop(int posIndex, string posSymbol)
{
   ulong ticket = PositionGetTicket(posIndex);
   if(!PositionSelectByTicket(ticket)) return;
   
   double currentPrice;
   double newSL;
   double currentSL = PositionGetDouble(POSITION_SL);
   double point = SymbolInfoDouble(posSymbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(posSymbol, SYMBOL_DIGITS);
   
   if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
   {
      currentPrice = SymbolInfoDouble(posSymbol, SYMBOL_BID);
      newSL = NormalizeDouble(currentPrice - InpTrailingDistance * point * 10, digits);
      
      if(newSL > currentSL && currentSL > 0)
      {
         ModifyPosition(ticket, posSymbol, newSL, PositionGetDouble(POSITION_TP));
      }
   }
   else
   {
      currentPrice = SymbolInfoDouble(posSymbol, SYMBOL_ASK);
      newSL = NormalizeDouble(currentPrice + InpTrailingDistance * point * 10, digits);
      
      if((newSL < currentSL && currentSL > 0) || currentSL == 0)
      {
         ModifyPosition(ticket, posSymbol, newSL, PositionGetDouble(POSITION_TP));
      }
   }
}

//+------------------------------------------------------------------+
//| Modify position SL/TP                                           |
//+------------------------------------------------------------------+
void ModifyPosition(ulong ticket, string symbol, double newSL, double newTP)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_SLTP;
   request.position = ticket;
   request.symbol = symbol;
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
   ObjectSetInteger(0, panelName, OBJPROP_XSIZE, 280);
   ObjectSetInteger(0, panelName, OBJPROP_YSIZE, 240);
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
   CreateLabel(lblSymbol, InpPanelX + 10, InpPanelY + 125, "Symbol: EURUSD");
   CreateLabel(lblSpread, InpPanelX + 10, InpPanelY + 145, "Spread: 0.0");
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
   ObjectSetString(0, lblSymbol, OBJPROP_TEXT, "Symbol: " + activeSymbol);
   
   if(activeSymbolIndex >= 0 && activeSymbolIndex < ArraySize(availableSymbols))
   {
      ObjectSetString(0, lblSpread, OBJPROP_TEXT, "Spread: " + DoubleToString(availableSymbols[activeSymbolIndex].spread, 1));
   }
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
   ObjectDelete(0, lblSymbol);
   ObjectDelete(0, lblSpread);
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