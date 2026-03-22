# Complete Dependencies Analysis
Generated: 02/22/2026 17:53:45

## Project Dependencies Overview

### Project Structure:
Total Projects: 17

**Project**: ApiInstant\ApiInstant
NuGet Packages: 3
  - Newtonsoft.Json
  - RestSharp
  - System.Runtime.Caching
Project References: 1
  - Extensions
Target Framework: net7.0

**Project**: Backend\Backend
NuGet Packages: 3
  - Microsoft.AspNet.WebApi.Core
  - Microsoft.AspNetCore.SignalR
  - Swashbuckle.AspNetCore
Project References: 2
  - Notifications
  - SharedLibrary
Target Framework: net7.0

**Project**: EFModel\EFModel
NuGet Packages: 4
  - Microsoft.EntityFrameworkCore
  - Microsoft.EntityFrameworkCore.Design
  - Microsoft.EntityFrameworkCore.SqlServer
  - Microsoft.EntityFrameworkCore.Tools
Project References: 4
  - ApiInstant
  - Extensions
  - SlackLibrary
  - WebHotelLib
Target Framework: net7.0

**Project**: Extensions\Extensions
Target Framework: net7.0

**Project**: MediciAgent\MediciAgent
NuGet Packages: 2
  - Microsoft.Extensions.Configuration
  - Microsoft.Extensions.Configuration.Json
Project References: 4
  - ApiInstant
  - EFModel
  - Notifications
  - SharedLibrary
Target Framework: net7.0

**Project**: MediciAutoCancellation\MediciAutoCancellation
NuGet Packages: 2
  - Microsoft.Extensions.Configuration
  - Microsoft.Extensions.Configuration.Json
Project References: 2
  - Notifications
  - SharedLibrary
Target Framework: net7.0

**Project**: MediciBuyRooms\MediciBuyRooms
NuGet Packages: 2
  - Microsoft.Extensions.Configuration
  - Microsoft.Extensions.Configuration.Json
Project References: 1
  - SharedLibrary
Target Framework: net7.0

**Project**: MediciUpdatePrices\MediciUpdatePrices
NuGet Packages: 2
  - Microsoft.Extensions.Configuration
  - Microsoft.Extensions.Configuration.Json
Project References: 2
  - ApiInstant
  - SharedLibrary
Target Framework: net7.0

**Project**: ModelsLibrary\ModelsLibrary
Target Framework: net7.0

**Project**: Notifications\Notifications
NuGet Packages: 2
  - SendGrid
  - Twilio
Project References: 1
  - Extensions
Target Framework: net7.0

**Project**: ProcessRevisedFile\ProcessRevisedFile
NuGet Packages: 3
  - CsvHelper
  - Microsoft.Extensions.Configuration
  - Microsoft.Extensions.Configuration.Json
Project References: 2
  - Extensions
  - SharedLibrary
Target Framework: net7.0

**Project**: SharedLibrary\SharedLibrary
NuGet Packages: 2
  - CsvHelper
  - System.Management
Project References: 4
  - EFModel
  - Extensions
  - ModelsLibrary
  - WebHotelLib
Target Framework: net7.0

**Project**: SlackLibrary\SlackLibrary
Project References: 1
  - Extensions
Target Framework: net7.0

**Project**: WebHotel\WebHotel
NuGet Packages: 2
  - Microsoft.Extensions.Configuration
  - Microsoft.Extensions.Configuration.Json
Project References: 3
  - SharedLibrary
  - SlackLibrary
  - WebHotelLib
Target Framework: net7.0

**Project**: WebHotelLib\WebHotelLib
NuGet Packages: 3
  - HtmlAgilityPack
  - Selenium.Support
  - Selenium.WebDriver
Project References: 2
  - Extensions
  - ModelsLibrary
Target Framework: net7.0

**Project**: WebHotelRevise\WebHotelRevise
NuGet Packages: 3
  - CsvHelper
  - Microsoft.Extensions.Configuration
  - Microsoft.Extensions.Configuration.Json
Project References: 3
  - SharedLibrary
  - SlackLibrary
  - WebHotelLib
Target Framework: net7.0

**Project**: WebInnstant\WebInnstant
NuGet Packages: 3
  - CsvHelper
  - Microsoft.Extensions.Configuration
  - Microsoft.Extensions.Configuration.Json
Project References: 1
  - WebHotelLib
Target Framework: net7.0


