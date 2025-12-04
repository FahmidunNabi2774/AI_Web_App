const synth = window.speechSynthesis;
const voiceSelect = document.getElementById('voice-select');
const listenBtn  = document.getElementById('listen-btn');
const stopBtn    = document.getElementById('stop-btn');

let currentUtterance = null;

function populateVoices() {
  const voices = synth.getVoices();
  voiceSelect.innerHTML = '<option disabled selected>Select a voice</option>';
  voices.forEach((voice, i) => {
    const option = document.createElement('option');
    option.value = i;
    option.textContent = `${voice.name} - ${voice.lang}`;
    voiceSelect.appendChild(option);
  });
}

function setUISpeaking(isSpeaking) {
  listenBtn.disabled = isSpeaking;
  stopBtn.disabled   = !isSpeaking;
}

function speakText() {
  const text = document.getElementById('tts-input').value.trim();
  const selectedIndex = voiceSelect.value;
  const voices = synth.getVoices();

  if (!text || !voices[selectedIndex]) return;

  // Stop anything already playing before starting new
  synth.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.voice = voices[selectedIndex];

  utterance.onstart = () => setUISpeaking(true);
  utterance.onend   = () => { setUISpeaking(false); currentUtterance = null; };
  utterance.onerror = () => { setUISpeaking(false); currentUtterance = null; };

  currentUtterance = utterance;
  synth.speak(utterance);
}

function stopSpeech() {
  // Cancels all queued/playing speech
  synth.cancel();
  setUISpeaking(false);
  currentUtterance = null;
}

// init
populateVoices();
if (typeof speechSynthesis !== 'undefined' && speechSynthesis.onvoiceschanged !== undefined) {
  speechSynthesis.onvoiceschanged = populateVoices;
}
// start with Stop disabled
setUISpeaking(false);

