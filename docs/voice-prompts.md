# Voice prompts

Drivers hear a short spoken prompt on each screen, in Hindi, Marathi or English. The words live in `web/src/driver/voicePrompts.ts`; this page copies them for the speaker check below. If the two differ, the code file is right.

## The nine prompts

| Prompt | Plays on | Hindi | Marathi | English |
| --- | --- | --- | --- | --- |
| `take_photo` | Trip screen | रसीद की फोटो लें। मोहर और साइन एक ही फोटो में आने चाहिए। | पावतीचा फोटो घ्या. शिक्का आणि सही एकाच फोटोत यायला हवी. | Take a photo of the receipt. The stamp and signature must be in the same photo. |
| `checking` | Checking | फोटो की जाँच हो रही है। कृपया गेट पर रुकें। | फोटो तपासला जात आहे. कृपया गेटवरच थांबा. | The photo is being checked. Please wait at the gate. |
| `blurred` | Phone check or AI retake: blurred | फोटो धुंधली है। फोन स्थिर रखें और फिर से फोटो लें। | फोटो अस्पष्ट आहे. फोन स्थिर धरा आणि पुन्हा फोटो घ्या. | The photo is blurred. Hold the phone still and take it again. |
| `dark` | Phone check or AI retake: dark | फोटो में अंधेरा है। रोशनी में जाकर फिर से फोटो लें। | फोटोत अंधार आहे. उजेडात जाऊन पुन्हा फोटो घ्या. | The photo is too dark. Move to the light and take it again. |
| `retake` | AI retake for any other reason | फोटो साफ़ नहीं है। पूरी रसीद फोटो में रखकर फिर से फोटो लें। | फोटो स्पष्ट नाही. पूर्ण पावती फोटोत घेऊन पुन्हा फोटो घ्या. | The photo is not clear. Get the whole receipt in the photo and take it again. |
| `saved_offline` | Saved on the phone | नेटवर्क नहीं है। फोटो फोन में सेव है, नेटवर्क आते ही अपने आप चली जाएगी। | नेटवर्क नाही. फोटो फोनमध्ये सेव्ह आहे, नेटवर्क आल्यावर आपोआप जाईल. | There is no network. The photo is saved on the phone and will send by itself. |
| `verified` | Done, verified | पीओडी सही है। आप जा सकते हैं। | पीओडी बरोबर आहे. तुम्ही जाऊ शकता. | The POD is verified. You can leave. |
| `can_leave` | Done, sent to office or no result yet | आप जा सकते हैं। ज़रूरत हुई तो ऑफिस आपको SMS करेगा। | तुम्ही जाऊ शकता. गरज पडल्यास ऑफिस तुम्हाला SMS करेल. | You can leave. The office will send you an SMS if needed. |
| `call_office` | Dead link, or a send the server refused | कुछ गड़बड़ है। कृपया ऑफिस को फोन करें। | काहीतरी अडचण आहे. कृपया ऑफिसला फोन करा. | Something is wrong. Please call the office. |

An AI retake for a blurred or dark photo uses the same prompt as the phone check, because the fix is the same. Every other retake reason, such as a missing stamp, gets `retake`, and the screen shows which field failed.

## How it plays

- The prompt plays when a screen opens, and again in the new language when the driver switches. Phones block sound until the first tap, so on a freshly opened link the speaker button is how the driver hears it.
- Hindi and English play recorded files from `web/public/voice/`. They were made with the voices built into macOS (Lekha for Hindi, Rishi for Indian English) by `cd web && npm run voice-files`.
- macOS has no Marathi voice and Gemini's speech model isn't available on this key, so Marathi has no files. The phone speaks the words with its own `mr-IN` voice. Android's Google speech engine has one; a phone without it reads them less well.
- If a file can't play (not stored yet, missing, or a format the phone can't decode), the phone speaks the words instead.
- The page stores every file in a cache the first time it opens with signal, and the service worker plays them from there, so prompts work in a dead zone.

## Replacing a voice with a recording

A native speaker's recording beats any synthetic voice. Save it as `web/public/voice/<language>/<prompt>.mp3`, mono, about 48 kbps. For Marathi, add `"mr"` to `FILE_LANGUAGES` in `web/src/driver/voice.ts`; a test then checks that all nine files exist. Phones pick up a replaced file in the background the next time it plays with signal.

## Speaker check

Ticket 17 isn't done until a Hindi speaker and a Marathi speaker have read the words above and listened to the Hindi files, and the result is recorded here.

| Language | Checked by | Date | Changes asked for |
| --- | --- | --- | --- |
| Hindi | Not yet checked | | |
| Marathi | Not yet checked | | |
