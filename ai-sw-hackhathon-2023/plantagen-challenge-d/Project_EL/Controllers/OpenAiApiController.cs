using Microsoft.AspNetCore.Mvc;
using System.IO;
using OpenAI_API;
using System.Threading.Tasks;
using System.Collections.Generic;

namespace Project_EL.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class OpenAiApiController : ControllerBase
    {
        OpenAIAPI api;
        public OpenAiApiController()
        {
            using (var sr = new StreamReader("apikey.txt"))
            {
                api = new OpenAIAPI(sr.ReadLine());
                sr.Close();
            }
        }

        public async Task<string> GetQueryResult(string query)
        {
            var chat = api.Chat.CreateConversation();
            chat.AppendUserInput(query);
            return await chat.GetResponseFromChatbotAsync();
        }

        public async IAsyncEnumerable<string> AnalyzeElectricityUsage()
        {
            var chat = api.Chat.CreateConversation();
            using (var sr = new StreamReader("prequery.txt")) 
            {
                chat.AppendUserInput(sr.ReadToEnd());
            }

            /*using (var sr = new StreamReader("Target_household_energy_data.csv"))
            {
                chat.AppendUserInput(sr.ReadToEnd());
            }*/

            using (var sr = new StreamReader("questions.txt"))
            {
                chat.AppendUserInput(sr.ReadToEnd());
            }

            var response = chat.StreamResponseEnumerableFromChatbotAsync();
            await foreach (var r in response)
            {
                yield return r;
            }
        }
    }
}
