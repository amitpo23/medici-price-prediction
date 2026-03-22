# 📊 מדריך הגדרת ניטור מתקדם - Medici Hotels

## 🎯 מערכת ניטור היברידית מומלצת

### 1. **Azure Application Insights - הגדרה מתקדמת**

#### שינויים נדרשים ב-Backend.csproj:
```xml
<PackageReference Include="Microsoft.ApplicationInsights.AspNetCore" Version="2.21.0" />
<PackageReference Include="Microsoft.Extensions.Logging.ApplicationInsights" Version="2.21.0" />
```

#### עדכון appsettings.json:
```json
{
  "ApplicationInsights": {
    "InstrumentationKey": "YOUR-INSTRUMENTATION-KEY",
    "ConnectionString": "InstrumentationKey=YOUR-KEY;IngestionEndpoint=https://westeurope-5.in.applicationinsights.azure.com/;LiveEndpoint=https://westeurope.livediagnostics.monitor.azure.com/"
  },
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning"
    },
    "ApplicationInsights": {
      "LogLevel": {
        "Default": "Information",
        "Microsoft.AspNetCore": "Warning"
      }
    }
  }
}
```

#### הגדרה ב-Program.cs:
```csharp
// הוספה לתחילת Program.cs
builder.Services.AddApplicationInsightsTelemetry();

// אופציונלי - טלמטריה מותאמת אישית
builder.Services.AddSingleton<ITelemetryInitializer, CustomTelemetryInitializer>();

// רישום לפני app.Run()
"Application Insights configured and running".Log();
```

---

### 2. **מערכת לוגים מקומית משופרת - SystemLogAdvanced.cs**

```csharp
using Microsoft.Extensions.Logging;
using System.Text.Json;

namespace Extensions
{
    public static class SystemLogAdvanced
    {
        private static readonly object _lockObj = new object();
        
        public static void LogAdvanced(this string message, 
                                     LogLevel level = LogLevel.Information,
                                     string category = "General",
                                     object? additionalData = null)
        {
            var logEntry = new
            {
                Timestamp = DateTime.UtcNow,
                Level = level.ToString(),
                Category = category,
                Message = message,
                MachineName = Environment.MachineName,
                ProcessId = Environment.ProcessId,
                ThreadId = Thread.CurrentThread.ManagedThreadId,
                AdditionalData = additionalData
            };
            
            var jsonLog = JsonSerializer.Serialize(logEntry, new JsonSerializerOptions 
            { 
                WriteIndented = true 
            });
            
            Console.WriteLine(jsonLog);
            
            lock (_lockObj)
            {
                try
                {
                    var logFileName = $"medici-{DateTime.Now:yyyy-MM-dd}.log";
                    var logPath = Path.Combine(@"C:\MediciLogs", logFileName);
                    
                    Directory.CreateDirectory(Path.GetDirectoryName(logPath)!);
                    
                    File.AppendAllText(logPath, jsonLog + Environment.NewLine);
                }
                catch { }
            }
        }
        
        public static void LogError(this Exception ex, string context = "")
        {
            LogAdvanced($"ERROR [{context}]: {ex.Message}", 
                       LogLevel.Error, 
                       "Exception",
                       new { 
                           ExceptionType = ex.GetType().Name,
                           StackTrace = ex.StackTrace?.Split('\n')[0] // רק השורה הראשונה
                       });
        }
        
        public static void LogBookingFlow(this string message, int? bookingId = null)
        {
            LogAdvanced(message, LogLevel.Information, "BookingFlow", 
                       new { BookingId = bookingId });
        }
        
        public static void LogApiCall(this string endpoint, object? requestData = null, object? responseData = null)
        {
            LogAdvanced($"API Call: {endpoint}", LogLevel.Information, "API",
                       new { 
                           Request = requestData,
                           Response = responseData,
                           Endpoint = endpoint
                       });
        }
    }
}
```

---

### 3. **מותאם אישית - Medici Performance Monitoring**

```csharp
// יצירת קובץ חדש: Monitoring/PerformanceTracker.cs
public class PerformanceTracker
{
    public class BookingMetrics
    {
        public int TotalOpportunities { get; set; }
        public int ProcessedSuccessfully { get; set; }
        public int ProcessingErrors { get; set; }
        public TimeSpan ProcessingTime { get; set; }
        public DateTime Timestamp { get; set; }
        public double SuccessRate => TotalOpportunities > 0 ? 
                                    (ProcessedSuccessfully / (double)TotalOpportunities) * 100 : 0;
    }
    
    public static async Task<BookingMetrics> GetBookingMetrics()
    {
        var metrics = new BookingMetrics
        {
            Timestamp = DateTime.UtcNow
        };
        
        try
        {
            // ממשק עם BaseEF לקבלת נתונים
            using var repo = Repository.Instance;
            
            // מד הזדמנויות שעובדו היום
            var opportunities = await GetTodaysOpportunities();
            metrics.TotalOpportunities = opportunities.Count;
            metrics.ProcessedSuccessfully = opportunities.Count(o => o.IsProcessedSuccessfully);
            metrics.ProcessingErrors = opportunities.Count(o => o.HasError);
            
            $"Booking Metrics: {metrics.SuccessRate:F1}% success rate ({metrics.ProcessedSuccessfully}/{metrics.TotalOpportunities})"
                .LogAdvanced(LogLevel.Information, "Metrics");
                
        }
        catch (Exception ex)
        {
            ex.LogError("GetBookingMetrics");
        }
        
        return metrics;
    }
}
```

---

### 4. **דשבורד לוגים מקומי - LogDashboard.html**

```html
<!DOCTYPE html>
<html>
<head>
    <title>Medici Hotels - Live Monitoring</title>
    <meta charset="utf-8">
    <style>
        body { font-family: 'Segoe UI', Arial; margin: 20px; }
        .metric-card { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 8px; }
        .success { border-left: 5px solid #4CAF50; }
        .warning { border-left: 5px solid #FF9800; }
        .error { border-left: 5px solid #F44336; }
        .log-entry { padding: 8px; margin: 2px 0; background: #fff; }
        #logContainer { height: 400px; overflow-y: auto; border: 1px solid #ddd; }
    </style>
</head>
<body>
    <h1>🏨 Medici Hotels - ניטור בזמן אמת</h1>
    
    <div class="metric-card success">
        <h3>📊 מטריקות הזמנות</h3>
        <p id="bookingMetrics">טוען...</p>
    </div>
    
    <div class="metric-card warning">
        <h3>🔄 תהליכים פעילים</h3>
        <p id="activeProcesses">טוען...</p>
    </div>
    
    <div class="metric-card error">
        <h3>🚨 שגיאות אחרונות</h3>
        <div id="recentErrors">טוען...</div>
    </div>
    
    <h3>📋 לוג בזמן אמת</h3>
    <div id="logContainer"></div>
    
    <script>
        // קוד JavaScript לקריאת קבצי לוג דרך local file API
        // או חיבור לאנדפוינט ב-Backend שיחזיר נתוני לוג
        
        async function loadMetrics() {
            try {
                const response = await fetch('/api/monitoring/metrics');
                const data = await response.json();
                document.getElementById('bookingMetrics').innerText = 
                    `שיעור הצלחה: ${data.successRate}% (${data.processed}/${data.total})`;
            } catch (e) {
                console.log('Metrics not available - running in local mode');
            }
            
            setTimeout(loadMetrics, 10000); // עדכון כל 10 שניות
        }
        
        loadMetrics();
    </script>
</body>
</html>
```

---

### 5. **API Endpoints לניטור**

```csharp
// Backend/Controllers/MonitoringController.cs
[ApiController]
[Route("api/[controller]")]
public class MonitoringController : ControllerBase
{
    [HttpGet("metrics")]
    public async Task<ActionResult> GetMetrics()
    {
        try
        {
            var metrics = await PerformanceTracker.GetBookingMetrics();
            return Ok(metrics);
        }
        catch (Exception ex)
        {
            ex.LogError("GetMetrics API");
            return StatusCode(500, "Error retrieving metrics");
        }
    }
    
    [HttpGet("logs")]
    public async Task<ActionResult> GetRecentLogs(int hours = 24)
    {
        try
        {
            var logs = await Repository.Instance.GetRecentLogs(hours);
            return Ok(logs);
        }
        catch (Exception ex)
        {
            ex.LogError("GetRecentLogs API");
            return StatusCode(500, "Error retrieving logs");
        }
    }
    
    [HttpGet("health")]
    public ActionResult GetSystemHealth()
    {
        var health = new
        {
            Timestamp = DateTime.UtcNow,
            DatabaseConnected = CheckDatabaseConnection(),
            ExternalAPIStatus = CheckExternalAPIs(),
            LoggingSystemActive = CheckLoggingSystem(),
            Status = "Healthy" // או Degraded, Down
        };
        
        return Ok(health);
    }
}
```

---

## 🚀 **תוכנית יישום מומלצת:**

### **שלב 1** (מיידי): 
- יישום SystemLogAdvanced.cs
- יצירת MonitoringController
- הקמת תיקיית C:\MediciLogs

### **שלב 2** (שבוע הבא):
- הגדרת Application Insights ב-Azure
- יישום PerformanceTracker
- יצירת דשבורד HTML מקומי

### **שלב 3** (חודש הבא):
- אינטגרציה מלאה עם Azure Monitoring
- התראות אוטומטיות בSlack
- דוחות ביצועים שבועיים

---

## 📞 מה שאוכל לעשות בהמשך:

1. **להטמיע את הקוד הנ"ל במערכת**
2. **ליצור כלי ניתוח לוגים אוטומטי**
3. **להגדיר Application Insights step-by-step** 
4. **לבנות דשבורד מותאם אישית**

רוצה שאתחיל עם אחד מהשלבים האלה?