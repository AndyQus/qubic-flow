<script setup>
import { watch, ref } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const particles = ref([])
let nextId = 0

const SYMBOLS = ['🪙', '💰', '💵', '🤑']
function sym() { return SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)] }

function playSound() {
  const type = store.soundStyle || 'kaching'
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    const now = ctx.currentTime
    const master = ctx.createGain()
    master.gain.value = 0.1
    master.connect(ctx.destination)

    function tone(freq, waveType, start, dur, vol) {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain); gain.connect(master)
      osc.type = waveType
      osc.frequency.value = freq
      gain.gain.setValueAtTime(vol, now + start)
      gain.gain.exponentialRampToValueAtTime(0.001, now + start + dur)
      osc.start(now + start); osc.stop(now + start + dur)
    }

    function noise(start, dur, vol, filterFreq = 300) {
      const samples = ctx.sampleRate * dur
      const buf = ctx.createBuffer(1, samples, ctx.sampleRate)
      const d = buf.getChannelData(0)
      for (let i = 0; i < samples; i++) d[i] = (Math.random() * 2 - 1) * Math.exp(-i / (samples * 0.4))
      const src = ctx.createBufferSource()
      src.buffer = buf
      const filter = ctx.createBiquadFilter()
      filter.type = 'bandpass'
      filter.frequency.value = filterFreq
      filter.Q.value = 1.5
      const gain = ctx.createGain()
      gain.gain.setValueAtTime(vol, now + start)
      src.connect(filter); filter.connect(gain); gain.connect(master)
      src.start(now + start); src.stop(now + start + dur)
    }

    if (type === 'kaching') {
      // Klassische Registrierkasse: mechanisches "Ka" + metallisches "Ching"
      noise(0, 0.06, 0.4, 180)               // "Ka" - mechanischer Klick
      tone(880,  'triangle', 0.05, 0.9, 0.4)  // A5 - Hauptring
      tone(1320, 'triangle', 0.05, 0.7, 0.25) // E6 - Oberton
      tone(440,  'sine',     0.05, 0.6, 0.15) // A4 - Basston
      tone(2640, 'sine',     0.06, 0.25, 0.1) // Sparkle
    } else if (type === 'coins') {
      // Münzen fallen: mehrere kurze Pings versetzt
      [0, 0.07, 0.13, 0.18, 0.22].forEach((t, i) => {
        const freq = 1200 - i * 80
        tone(freq, 'triangle', t, 0.35 - i * 0.04, 0.3 - i * 0.04)
        noise(t, 0.03, 0.15, 400)
      })
    } else if (type === 'chime') {
      // Sanfte Glocke: ruhiger Eingang
      tone(523, 'sine', 0,    1.2, 0.3)  // C5
      tone(659, 'sine', 0.08, 1.0, 0.2)  // E5
      tone(784, 'sine', 0.16, 0.8, 0.15) // G5
      tone(1046,'sine', 0.24, 0.6, 0.1)  // C6
    }
  } catch {}
}

function add(p, lifetime) {
  particles.value.push(p)
  setTimeout(() => { particles.value = particles.value.filter(x => x.id !== p.id) }, lifetime)
}

function spawnCoinRain() {
  for (let i = 0; i < 24; i++) {
    setTimeout(() => {
      add({
        id: nextId++, symbol: sym(), cls: 'p-coin-rain',
        style: {
          left: Math.random() * 94 + '%',
          animationDuration: (1.0 + Math.random() * 1.2) + 's',
          fontSize: (1.1 + Math.random() * 0.9) + 'rem',
        }
      }, 2500)
    }, Math.random() * 900)
  }
}

function spawnBurst() {
  const count = 20
  for (let i = 0; i < count; i++) {
    const angle = (i / count) * 360
    const dist  = 130 + Math.random() * 90
    const rad   = (angle * Math.PI) / 180
    add({
      id: nextId++, symbol: sym(), cls: 'p-money-burst',
      style: {
        '--tx': (Math.cos(rad) * dist) + 'px',
        '--ty': (Math.sin(rad) * dist) + 'px',
        left: '50%', top: '45%',
        fontSize: (1.1 + Math.random() * 0.8) + 'rem',
        animationDuration: (0.55 + Math.random() * 0.35) + 's',
      }
    }, 1100)
  }
}

function spawnFloating() {
  for (let i = 0; i < 18; i++) {
    setTimeout(() => {
      const dir = Math.random() > 0.5 ? 1 : -1
      add({
        id: nextId++, symbol: sym(), cls: 'p-floating',
        style: {
          left: (4 + Math.random() * 88) + '%',
          '--sx': (dir * (10 + Math.random() * 20)) + 'px',
          animationDuration: (1.8 + Math.random() * 1.4) + 's',
          fontSize: (1.0 + Math.random() * 0.9) + 'rem',
        }
      }, 3600)
    }, Math.random() * 700)
  }
}

function trigger() {
  if (store.moneySound) playSound()
  if      (store.moneyAnim === 'coin-rain')      spawnCoinRain()
  else if (store.moneyAnim === 'money-burst')    spawnBurst()
  else if (store.moneyAnim === 'floating-coins') spawnFloating()
}

watch(() => store.newEventIds.length, (n, o) => { if (n > o) trigger() })
</script>

<template>
  <div class="money-overlay" aria-hidden="true">
    <span
      v-for="p in particles"
      :key="p.id"
      :class="['money-particle', p.cls]"
      :style="p.style"
    >{{ p.symbol }}</span>
  </div>
</template>
