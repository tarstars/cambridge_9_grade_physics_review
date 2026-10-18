"""Question-level topic suggestions; all suggestions remain editable by the learner.

The main topic names follow the local Cambridge 9702 2025–2027 syllabus.
Historical content is kept in separate categories rather than forced into today's syllabus.
"""
import re
from bisect import bisect_left

# id, subject area, syllabus topic, weighted phrases found in a question's own text
TOPIC_RULES = [
    ("units", "Measurement", "Physical quantities and units", [
        (9, r"\bSI base|base quantit|base unit|\bprefix|\bhomogene|dimensional|percentage uncertainty|percentage error|(?:measured|expressed) in|unit (?:of|for)"),
        (7, r"uncertaint|systematic error|random error|precision|accuracy|micrometer|vernier"),
        (5, r"scalar|vector|significant figure|physical quantit|\bunits?\b")]),
    ("kinematics", "Mechanics", "Kinematics", [
        (9, r"projectile|displacement.?time|velocity.?time|speed.?time|uniform acceleration|definition of velocity|definition of acceleration"),
        (6, r"free fall|thrown|falling|dropped|travels? from rest|initial velocity|final velocity|time of flight"),
        (3, r"\bacceleration|\bvelocity|\bdisplacement|\bdeceleration")]),
    ("dynamics", "Mechanics", "Dynamics", [
        (10, r"momentum|collision|collid|impulse|Newton.s (?:first|second|third)|\bF\s*=\s*ma"),
        (8, r"resultant force|net force|rate of change of momentum|action and reaction"),
        (4, r"terminal (?:speed|velocity)|friction|air resistance|accelerating force")]),
    ("forces", "Mechanics", "Forces, density and pressure", [
        (10, r"\btorque|principle of moments|moment of (?:a |the )?force|\bcouple\b|upthrust|hydrostatic|Archimedes"),
        (8, r"\bequilibrium|\bhinge|\bpivot|\bbuoyan|centre of (?:gravity|mass)"),
        (5, r"\bdensity|\bpressure|\btension|resultant of|forces acting")]),
    ("energy", "Mechanics", "Work, energy and power", [
        (9, r"kinetic energy|gravitational potential energy|work done|energy conservation|conservation of energy|\befficiency"),
        (7, r"\bpower\b|\bjoules?\b|\bwatts?\b|potential energy gained"),
        (4, r"energy transferred|energy dissipated|energy lost|energy supplied")]),
    ("deformation", "Mechanics", "Deformation of solids", [
        (12, r"Young.s modulus|Hooke.s law|\bstress\b|\bstrain\b|elastic limit|limit of proportionality"),
        (8, r"\bextension|spring constant|elastic potential energy|plastic deformation|elastic deformation"),
        (3, r"\bspring\b|stretched wire")]),
    ("waves", "Waves", "Waves", [
        (10, r"Doppler|transverse wave|longitudinal wave|progressive wave|electromagnetic spectrum|polarisation|polarization"),
        (7, r"\bwavelength|wave speed|speed of (?:sound|light)|intensity of (?:the |a )?(?:sound|wave)|\bwavefront"),
        (3, r"\bfrequency|\bamplitude|\bwave\b|\bwaves\b")]),
    ("superposition", "Waves", "Superposition", [
        (12, r"interference|diffraction|\bfringe|double.?slit|\bgrating|coherent|stationary wave|standing wave"),
        (8, r"superposition|path difference|\bantinodes?\b|\bnodes?\b|Malus"),
        (5, r"two sources|phase difference")]),
    ("electricity", "Electricity and magnetism", "Electricity", [
        (10, r"\bresistivity|\bohm.s law|drift (?:speed|velocity)|charge carriers|I\s*=\s*Anvq"),
        (7, r"definition of (?:electric )?current|definition of (?:potential difference|electromotive)|\bcoulomb|\bemf\b|e\.m\.f"),
        (5, r"\belectric current|\bresistance|\bcharge flow|current.?voltage|I.?V characteristic")]),
    ("circuits", "Electricity and magnetism", "D.C. circuits", [
        (11, r"potential divider|Kirchhoff|\bpotentiometer|\bthermistor|light.dependent resistor|\bLDR\b|internal resistance"),
        (8, r"\bcircuit|series (?:combination|connection)|parallel (?:combination|connection)|\bresistors?"),
        (4, r"\bvoltmeter|\bammeter|terminal (?:voltage|potential difference)|\bcell\b|\bbattery")]),
    ("particles", "Atomic and nuclear physics", "Particle physics", [
        (12, r"\bquarks?\b|\bleptons?\b|\bbaryons?\b|\bhadrons?\b|\bmesons?\b|\bantiquark|\bstrangeness"),
        (9, r"weak interaction|strong interaction|fundamental particles|annihilat|Rutherford|alpha.particle scattering"),
        (6, r"\bpositron|\bantiparticle|\bneutrino")]),
    ("circular", "Mechanics", "Motion in a circle", [
        (12, r"centripetal|circular motion|angular (?:speed|velocity|displacement)|moves in a circle"),
        (7, r"vertical circle|horizontal circle|uniform circle|\bradians?\b"),
        (3, r"\borbit|\brotat")]),
    ("gravitation", "Fields", "Gravitational fields", [
        (12, r"gravitational (?:field|potential|force)|Newton.s law of gravitation|geostationary|escape (?:speed|velocity)"),
        (8, r"\bsatellite|orbital (?:period|radius|speed)|\bKepler"),
        (3, r"\borbit|\bplanet|\bEarth")]),
    ("temperature", "Thermal physics", "Temperature", [
        (11, r"thermodynamic (?:scale|temperature)|absolute zero|Celsius|\bthermometer|\bthermocouple"),
        (6, r"\bkelvin|thermal equilibrium|temperature scale")]),
    ("gases", "Thermal physics", "Ideal gases", [
        (12, r"ideal gas|kinetic theory|\bBrownian|mean.square (?:speed|velocity)|Boyle.s law|\bpV\s*=\s*nRT"),
        (8, r"gas molecules|gas constant|Boltzmann|gas pressure|molecular (?:speed|mass)|root.mean.square"),
        (4, r"\bmoles?\b|\bAvogadro|gas in|gas is|gas has")]),
    ("thermodynamics", "Thermal physics", "Thermodynamics", [
        (12, r"specific heat|heat capacity|specific latent|latent heat|internal energy|first law of thermodynamics"),
        (8, r"\badiabatic|\bisothermal|\bcalorimet|\bmelting|\bboiling|\bevaporat"),
        (4, r"thermal energy|\bheater|temperature rise|\bheating|\bcooling")]),
    ("oscillations", "Mechanics", "Oscillations", [
        (12, r"simple harmonic|\bs\.h\.m|\bSHM\b|\bresonance|\bdamping|\bdamped|natural frequency"),
        (8, r"\boscillat|\bpendulum|restoring force|angular frequency"),
        (3, r"\bamplitude|time period")]),
    ("electric-fields", "Fields", "Electric fields", [
        (12, r"electric field|electric potential|Coulomb.s law|\bpermittivity"),
        (8, r"point charge|charged plates|parallel plates|electrostatic|force on (?:a |the )?charge"),
        (4, r"\bcharged sphere|\bfield strength|\bequipotential")]),
    ("capacitance", "Electricity and magnetism", "Capacitance", [
        (14, r"\bcapacitor|\bcapacitance|\bdielectric"),
        (7, r"time constant|charging curve|discharging curve|\bfarad")]),
    ("magnetism", "Electricity and magnetism", "Magnetic fields", [
        (12, r"magnetic (?:field|flux|force)|electromagnetic induction|Faraday|Lenz|\bHall (?:effect|voltage|probe)|\bsolenoid"),
        (9, r"\btransformer|\btesla|\bweber|flux linkage|induced (?:emf|e\.m\.f|current)|\binductance"),
        (5, r"\bmagnet|\bcoil|\bgalvanometer")]),
    ("ac", "Electricity and magnetism", "Alternating currents", [
        (13, r"alternating (?:current|voltage)|\brectifi|\bsmoothing|\bhalf.wave|\bfull.wave"),
        (9, r"r\.m\.s|root.mean.square (?:current|voltage)|\ba\.c\.|\bAC supply"),
        (6, r"\bdiodes?\b|peak (?:current|voltage)")]),
    ("quantum", "Atomic and nuclear physics", "Quantum physics", [
        (13, r"photoelectric|de Broglie|\bphotons?\b|work function|threshold frequency|wave.particle|stopping (?:voltage|potential)"),
        (10, r"energy levels|emission (?:line|spectrum)|absorption (?:line|spectrum)|Planck|electron diffraction"),
        (6, r"\belectronvolt|\beV\b|\bspectra\b")]),
    ("nuclear", "Atomic and nuclear physics", "Nuclear physics", [
        (13, r"half.life|\bradioactiv|\bfission|\bfusion|binding energy|mass defect|decay constant|\bnucleon"),
        (9, r"alpha (?:decay|radiation|emission)|beta (?:decay|radiation|emission)|gamma (?:ray|radiation)|\bnuclei|\bnucleus|\bisotope"),
        (6, r"\bactivity|background (?:count|radiation)|\bdecay|\bneutron")]),
    ("medical", "Applications", "Medical physics", [
        (14, r"\bMRI\b|magnetic resonance imaging|\bCT scan|\bPET scan|positron emission tomography|acoustic impedance"),
        (10, r"\bultrasound|\bultrasonic|\bX.ray|\bX.rays|attenuation coefficient|medical imaging"),
        (5, r"\btissue|\btransducer|\btomography")]),
    ("astronomy", "Applications", "Astronomy and cosmology", [
        (13, r"\bHubble|\bred.shift|\bredshift|\bcosmolog|\bluminosity|\bWien|Stefan.Boltzmann|\bparsec"),
        (10, r"\bgalax|standard candle|black.body|\bBig Bang|cosmic microwave|\bsupernova|\bCepheid"),
        (6, r"\bstars?\b|\bstellar|expanding universe|\blight.year")]),
    ("practical", "Practical skills", "Experiments, graphs and data analysis", [
        (12, r"design (?:an? |the )?experiment|plan (?:an? |the )?experiment|in this experiment|record your (?:results|readings)|six sets of readings"),
        (9, r"sources? of error|improvements? to|line of best fit|error bars|safety precautions|independent variable|dependent variable"),
        (5, r"plot a graph|\bgradient|y.intercept|percentage difference|measure and record")]),
    ("electronics", "Historical syllabus", "Electronics and operational amplifiers", [
        (14, r"operational amplifier|op.amp|\bcomparator|\blogic gate|\bNAND|\bNOR gate|\bflip.flop|\btransistor"),
        (9, r"feedback resistor|inverting amplifier|non.inverting|light.emitting diode|digital electronics")]),
    ("communications", "Historical syllabus", "Communication systems", [
        (14, r"\bmodulation|\bbandwidth|\bcarrier wave|\bcarrier frequency|analogue.to.digital|digital.to.analogue|\bsatellite communication"),
        (10, r"\btelecommunicat|\bsideband|\bsampling frequency|optical fibre|optical fiber|signal.to.noise")]),
    ("fluids", "Historical syllabus", "Fluid dynamics", [
        (14, r"Bernoulli|Stokes. law|\bviscosity|\bReynolds|\blaminar|\bturbulent|streamline flow|equation of continuity")]),
]

TOPICS = [{"id": key, "area": area, "label": label} for key, area, label, rules in TOPIC_RULES]
TOPICS.append({"id": "unclassified", "area": "Review", "label": "Topic needs review"})
TOPIC_IDS = {topic["id"] for topic in TOPICS}
COMPILED = [(key, [(weight, re.compile(pattern, re.I)) for weight, pattern in rules])
            for key, _, _, rules in TOPIC_RULES]


def classify(text, component=None):
    original_text = text
    if component == "1":
        # Answer distractors often mention unrelated topics. Classify the stem instead.
        lines = text.splitlines()
        positions = {label: [i for i, line in enumerate(lines) if re.match(rf"^{label}(?:\s|$)", line.strip())]
                     for label in "ABCD"}
        if all(positions.values()):
            choices = []
            for last in positions["D"]:
                sequence = [last]
                for label in "CBA":
                    index = bisect_left(positions[label], sequence[0]) - 1
                    if index < 0:
                        break
                    sequence.insert(0, positions[label][index])
                if len(sequence) == 4:
                    choices.append(sequence)
            if choices:
                start = min(choices, key=lambda indices: indices[-1] - indices[0])[0]
                if start > 0:
                    text = "\n".join(lines[:start])
        for i, line in enumerate(lines):
            if re.match(r"^A\s.+\sB\s.+\sC\s.+\sD\s", line.strip()) and i:
                text = "\n".join(lines[:i])
                break
    text = text.replace("\n", " ").replace("–", "-").replace("−", "-")
    scores, evidence = {}, {}
    for key, rules in COMPILED:
        hits, score = [], 0
        for weight, pattern in rules:
            matches = list(pattern.finditer(text))
            if matches:
                score += weight * min(2, len(matches))
                hits.extend(match.group(0) for match in matches[:2])
        if score:
            scores[key], evidence[key] = score, list(dict.fromkeys(hits))[:6]
    # These components explicitly assess experimental or planning skills.
    if component in ("3", "5"):
        scores["practical"] = max(scores.get("practical", 0), 12)
        evidence.setdefault("practical", []).append("Practical/planning paper")
    ordered = sorted(scores, key=lambda key: -scores[key])
    if not ordered or scores[ordered[0]] < 7:
        if component == "1" and text.strip() != original_text.strip():
            fallback = classify(original_text)
            fallback["confidence"] = "review"
            return fallback
        return {"topics": ["unclassified"], "confidence": "review", "evidence": {}}
    first = ordered[0]
    selected = [first] + [key for key in ordered[1:] if scores[key] >= max(9, scores[first] * .5)][:2]
    confidence = "suggested" if scores[first] >= 12 else "review"
    return {"topics": selected, "confidence": confidence,
            "evidence": {key: evidence[key] for key in selected}}
