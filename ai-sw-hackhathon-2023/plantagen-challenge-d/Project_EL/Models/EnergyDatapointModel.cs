using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Project_EL.Models
{
    public class EnergyDatapointModel
    {
        public DateTime Timestamp { get; set; }
        public double TotalEnergyConsumed { get; set; }
        public double TemperatureCelcius { get; set; }
        public double SpotPrice { get; set; }
    }
}
