// The words of every voice prompt, in the three languages a driver can pick. This file is the one
// source: the app speaks from it, and scripts/make-voice-files.ts turns it into audio files. Keep
// it plain TypeScript with no imports, so Node can run that script straight from it.
//
// Short sentences in everyday words, said the way a supervisor at the gate would say them. A Hindi
// and a Marathi speaker check them before the ticket is done; see docs/voice-prompts.md.

export const PROMPTS = {
  take_photo: {
    hi: "रसीद की फोटो लें। मोहर और साइन एक ही फोटो में आने चाहिए।",
    mr: "पावतीचा फोटो घ्या. शिक्का आणि सही एकाच फोटोत यायला हवी.",
    en: "Take a photo of the receipt. The stamp and signature must be in the same photo.",
  },
  checking: {
    hi: "फोटो की जाँच हो रही है। कृपया गेट पर रुकें।",
    mr: "फोटो तपासला जात आहे. कृपया गेटवरच थांबा.",
    en: "The photo is being checked. Please wait at the gate.",
  },
  blurred: {
    hi: "फोटो धुंधली है। फोन स्थिर रखें और फिर से फोटो लें।",
    mr: "फोटो अस्पष्ट आहे. फोन स्थिर धरा आणि पुन्हा फोटो घ्या.",
    en: "The photo is blurred. Hold the phone still and take it again.",
  },
  dark: {
    hi: "फोटो में अंधेरा है। रोशनी में जाकर फिर से फोटो लें।",
    mr: "फोटोत अंधार आहे. उजेडात जाऊन पुन्हा फोटो घ्या.",
    en: "The photo is too dark. Move to the light and take it again.",
  },
  retake: {
    hi: "फोटो साफ़ नहीं है। पूरी रसीद फोटो में रखकर फिर से फोटो लें।",
    mr: "फोटो स्पष्ट नाही. पूर्ण पावती फोटोत घेऊन पुन्हा फोटो घ्या.",
    en: "The photo is not clear. Get the whole receipt in the photo and take it again.",
  },
  saved_offline: {
    hi: "नेटवर्क नहीं है। फोटो फोन में सेव है, नेटवर्क आते ही अपने आप चली जाएगी।",
    mr: "नेटवर्क नाही. फोटो फोनमध्ये सेव्ह आहे, नेटवर्क आल्यावर आपोआप जाईल.",
    en: "There is no network. The photo is saved on the phone and will send by itself.",
  },
  verified: {
    hi: "पीओडी सही है। आप जा सकते हैं।",
    mr: "पीओडी बरोबर आहे. तुम्ही जाऊ शकता.",
    en: "The POD is verified. You can leave.",
  },
  can_leave: {
    hi: "आप जा सकते हैं। ज़रूरत हुई तो ऑफिस आपको SMS करेगा।",
    mr: "तुम्ही जाऊ शकता. गरज पडल्यास ऑफिस तुम्हाला SMS करेल.",
    en: "You can leave. The office will send you an SMS if needed.",
  },
  call_office: {
    hi: "कुछ गड़बड़ है। कृपया ऑफिस को फोन करें।",
    mr: "काहीतरी अडचण आहे. कृपया ऑफिसला फोन करा.",
    en: "Something is wrong. Please call the office.",
  },
} as const;
