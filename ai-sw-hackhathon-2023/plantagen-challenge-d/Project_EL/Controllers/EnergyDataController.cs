using Microsoft.AspNetCore.Mvc;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using CsvHelper;
using Microsoft.AspNetCore.Http;
using Project_EL.Services;
using Microsoft.Extensions.Logging;

namespace Project_EL.Controllers
{
    [Controller]
    public class EnergyDataController : Controller
    {
        private readonly ILogger<EnergyDataController> _logger;

        public EnergyDataController(ILogger<EnergyDataController> logger)
        {
            _logger = logger;
        }

        public IActionResult Index()
        {
            return View();
        }

        public IActionResult Upload()
        {
            return View();
        }

        [HttpPost]
        public ActionResult UploadCSV(IFormFile file)
        {
            _logger.LogInformation("Entering UploadCSV");

            CsvDataService csvDataService = new();

            if (file == null || file.Length == 0)
            {
                _logger.LogWarning("No file selected or file is empty.");
                // Redirect to the Upload view with an error message
                TempData["ErrorMessage"] = "No file selected or file is empty.";
                return RedirectToAction("Upload");
            }

            try
            {
                var records = csvDataService.ParseCsvFile(file);
                _logger.LogInformation($"Processed {records.Count} EnergyDataPoints.");

                // Further processing or passing the data to the view
                return View("Results", records);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "An error occurred while processing the CSV file.");
                // Redirect to an error view or back to the Upload view with an error message
                TempData["ErrorMessage"] = "An error occurred while processing the file.";
                return RedirectToAction("Upload");
            }
        }
    }
}
