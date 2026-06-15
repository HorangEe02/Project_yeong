// AJIN Mobile · Tweaks integration
// Floating panel for tweaking Liquid Glass intensity, Gold accent, Bezel
// tone, Dynamic Island shape, and which sections show on the canvas.

const AJIN_TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "style": "neural",
  "lgBlur": 36,
  "lgSat": 1.8,
  "lgEdge": 1,
  "lgTintA": 0.08,
  "goldH": 1,
  "neGlow": 1,
  "neAnim": 1,
  "bezelTone": "titanium",
  "island": "pill",
  "bezelHi": true,
  "sheen": true,
  "reflect": true,
  "showDark": true,
  "showLight": true,
  "showPad": true
}/*EDITMODE-END*/;

function AjinTweaks({ tweaks, setTweak }) {
  return (
    <TweaksPanel title="AJIN Mobile · Tweaks">
      <TweakSection label="Design language" />
      <TweakRadio label="Style"
                   value={tweaks.style}
                   options={['neural', 'classic']}
                   onChange={v => setTweak('style', v)} />
      <TweakSlider label="Neural glow"   value={tweaks.neGlow} min={0} max={1.4} step={0.05}
                   onChange={v => setTweak('neGlow', v)} />
      <TweakSlider label="Neuron motion" value={tweaks.neAnim} min={0} max={1.2} step={0.05}
                   onChange={v => setTweak('neAnim', v)} />

      <TweakSection label="Liquid Glass" />
      <TweakSlider label="Blur"          value={tweaks.lgBlur}  min={12}  max={64}  step={2}    unit="px"
                   onChange={v => setTweak('lgBlur', v)} />
      <TweakSlider label="Saturation"    value={tweaks.lgSat}   min={1}   max={2.4} step={0.05}
                   onChange={v => setTweak('lgSat', v)} />
      <TweakSlider label="Specular edge" value={tweaks.lgEdge}  min={0}   max={1.4} step={0.05}
                   onChange={v => setTweak('lgEdge', v)} />
      <TweakSlider label="Lens tint"     value={tweaks.lgTintA} min={0}   max={0.25} step={0.01}
                   onChange={v => setTweak('lgTintA', v)} />

      <TweakSection label="Gold accent" />
      <TweakSlider label="Hue intensity" value={tweaks.goldH}   min={0}   max={1.4} step={0.05}
                   onChange={v => setTweak('goldH', v)} />

      <TweakSection label="Device frame" />
      <TweakSelect label="Bezel tone" value={tweaks.bezelTone}
                   options={['titanium', 'space', 'natural']}
                   onChange={v => setTweak('bezelTone', v)} />
      <TweakRadio  label="Island"     value={tweaks.island}
                   options={['pill', 'wide', 'minimal']}
                   onChange={v => setTweak('island', v)} />
      <TweakToggle label="Bezel highlight" value={tweaks.bezelHi}
                   onChange={v => setTweak('bezelHi', v)} />
      <TweakToggle label="Screen sheen"    value={tweaks.sheen}
                   onChange={v => setTweak('sheen', v)} />
      <TweakToggle label="Bottom reflect"  value={tweaks.reflect}
                   onChange={v => setTweak('reflect', v)} />

      <TweakSection label="Sections" />
      <TweakToggle label="iPhone · Dark"  value={tweaks.showDark}
                   onChange={v => setTweak('showDark', v)} />
      <TweakToggle label="iPhone · Light" value={tweaks.showLight}
                   onChange={v => setTweak('showLight', v)} />
      <TweakToggle label="iPad sections"  value={tweaks.showPad}
                   onChange={v => setTweak('showPad', v)} />
    </TweaksPanel>
  );
}

// Apply tweak values to the root .aj-mobile element (via CSS custom props)
function applyAjinTweaks(t) {
  const root = document.querySelector('.aj-mobile');
  if (!root) return;
  root.style.setProperty('--lg-blur',   t.lgBlur + 'px');
  root.style.setProperty('--lg-sat',    t.lgSat);
  root.style.setProperty('--lg-edge',   t.lgEdge);
  root.style.setProperty('--lg-tint-a', t.lgTintA);
  root.style.setProperty('--aj-gold-h', t.goldH);
  root.style.setProperty('--ne-glow',   t.neGlow != null ? t.neGlow : 1);
  root.style.setProperty('--ne-anim',   t.neAnim != null ? t.neAnim : 1);
  document.documentElement.setAttribute('data-neural', t.style === 'neural' ? 'on' : 'off');
}

window.AjinTweaks = AjinTweaks;
window.AJIN_TWEAK_DEFAULTS = AJIN_TWEAK_DEFAULTS;
window.applyAjinTweaks = applyAjinTweaks;
