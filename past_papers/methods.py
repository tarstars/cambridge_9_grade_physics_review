"""Specific, editable question patterns, identified from a question's own stem.

Rules require evidence of a particular operation. There is deliberately no
fallback from a broad syllabus topic to a purported solution method.
"""
import re
from bisect import bisect_left
from .topics import TOPICS

VERSION = "4"
TYPES = []


def pattern(key, topic, label, approach, *requirements, exclude=None):
    TYPES.append({"id": key, "topic": topic, "label": label, "approach": approach,
                  "requirements": requirements, "exclude": exclude})


pattern("si-base-quantity", "units", "Identify an SI base quantity",
        "Decide whether each option names a physical quantity or a unit. Then compare the quantities with the seven SI base quantities: time, length, mass, electric current, thermodynamic temperature, amount of substance and luminous intensity.",
        r"\bbase quantit(?:y|ies)\b")
pattern("si-base-unit", "units", "Identify an SI base unit",
        "Separate the name of a quantity from its unit. The SI base units are second, metre, kilogram, ampere, kelvin, mole and candela.",
        r"\bbase units?\b", r"which|identify|select|underline|name|state|list",
        exclude=r"express|constant|homogene|units? (?:of|for)|definition|derived")
pattern("derive-base-units", "units", "Express a derived unit using base units",
        "Start with the defining equation. Replace every quantity by its SI base units, then simplify the powers of kg, m, s, A and K. Treat a constant in the same way by rearranging its equation first.",
        r"\bbase units?\b", r"express|derived|constant|units? (?:of|for)|definition|determine|show that|calculate")
pattern("dimensional-consistency", "units", "Check an equation using its units",
        "Reduce each term on both sides to base units. Terms added together must have the same units, and the units on the two sides must agree. Agreement is necessary but does not prove an equation is physically correct.",
        r"homogene|dimensionally|consistent.{0,25}units|units.{0,60}(?:correct|equation)")
pattern("compare-units", "units", "Find quantities with equivalent units",
        "Write the unit of each candidate using its defining equation, reduce it to base units, and compare exponents. Quantities can have the same units while describing different physical ideas.",
        r"same (?:si )?units?|equivalent (?:si )?units?|units?.{0,35}(?:same as|equivalent to)")
pattern("unit-prefix", "units", "Convert SI prefixes and powers of ten",
        "Write each prefix as a power of ten before substituting. Apply powers to the conversion factor too: converting a length to an area or volume squares or cubes the factor.",
        r"\bprefix(?:es)?\b|\b(?:nano|micro|milli|kilo|mega|giga|pico)\b",
        r"convert|equivalent|power|prefix|express|which")
pattern("uncertainty-propagation", "units", "Propagate uncertainty in a calculated result",
        "For addition or subtraction, add absolute uncertainties. For products and quotients, add fractional uncertainties. A power multiplies the fractional uncertainty by the magnitude of that power; convert to a percentage or absolute uncertainty only at the end.",
        r"uncertaint", r"calculated|calculat.{0,40}(?:volume|area|resistance|density)|volume|surface area|product|quotient|raised|power of|expression|formula|equation|intensity|\bresistance\b")
pattern("uncertainty-conversion", "units", "Convert between absolute and percentage uncertainty",
        "Use percentage uncertainty = absolute uncertainty / measured value × 100. Rearrange to recover an absolute uncertainty. Keep the value and its absolute uncertainty in the same units.",
        r"absolute uncertainty", r"percentage uncertainty|fractional uncertainty")
pattern("random-systematic-errors", "units", "Distinguish random and systematic errors",
        "A systematic error shifts results in a consistent way; repeated readings do not remove it. Random errors create scatter, so repeats and averaging help. Relate accuracy to closeness to the accepted value and precision to spread.",
        r"random error|systematic error|zero error|precision.{0,70}accuracy|accuracy.{0,70}precision")
pattern("scalar-vector", "units", "Distinguish scalar and vector quantities",
        "A scalar has magnitude only. A vector also has direction and must combine by vector addition. Test the physical quantity itself rather than the way its unit is written.",
        r"\bscalar|\bvector", r"which|identify|state|classif|list|distinguish")
pattern("vector-components", "forces", "Resolve a vector into perpendicular components",
        "Draw perpendicular axes and mark the angle to the original vector. The component adjacent to the angle uses cosine; the opposite component uses sine. Check signs using the directions of the axes.",
        r"\bcomponent(?:s)?\b", r"force|velocity|vector|horizontal|vertical")
pattern("resultant-vectors", "forces", "Find the resultant of vectors",
        "Add components along each axis, or draw a head-to-tail vector triangle. Find the resultant magnitude using Pythagoras for perpendicular components, then determine its direction.",
        r"resultant", r"force|vector|velocity|displacement")
pattern("motion-graph-gradient", "kinematics", "Read velocity or acceleration from a motion graph",
        "Identify the axes first. The gradient of displacement–time is velocity; the gradient of velocity–time is acceleration. Use a tangent for an instantaneous value and include the axis scale factors.",
        r"graph|gradient|variation with time", r"displacement|velocity|speed", r"acceleration|gradient|tangent")
pattern("motion-graph-area", "kinematics", "Find displacement from the area under a velocity graph",
        "Find signed area under the velocity–time graph. Area below the time axis contributes negative displacement. For total distance, add the magnitudes of all the areas.",
        r"graph|variation with time", r"velocity|speed", r"displacement|distance|area")
pattern("constant-acceleration", "kinematics", "Solve motion with constant acceleration",
        "Choose a positive direction, list u, v, a, s and t with signs, then select a constant-acceleration equation that contains the known quantities and the required unknown.",
        r"uniform acceleration|constant acceleration|accelerates uniformly|decelerates uniformly|falls freely|free fall|dropped from rest")
pattern("projectile-components", "kinematics", "Separate horizontal and vertical projectile motion",
        "Resolve the launch velocity. With negligible drag, horizontal velocity is constant and vertical acceleration is g downward. Time is shared by the two components; solve the vertical motion to find flight time.",
        r"projectile|projected.{0,60}(?:horizontal|angle)|thrown.{0,60}(?:horizontal|angle)")
pattern("newton-second-law", "dynamics", "Use resultant force and F = ma",
        "Draw all forces on one chosen object. Sum signed force components in the direction of acceleration, set the resultant equal to ma, and distinguish a single applied force from the resultant.",
        r"resultant force|net force|newton.s second law|resultant.{0,30}acceleration")
pattern("newton-third-law", "dynamics", "Identify a Newton’s third-law pair",
        "The paired forces are equal and opposite, act on different objects, and arise from the same interaction. Weight and the normal force on one object are not a third-law pair.",
        r"newton.s third|action.{0,25}reaction|third.law pair")
pattern("momentum-collision", "dynamics", "Conserve momentum in a collision or explosion",
        "Choose a system and a positive direction. If external impulse is negligible, total signed momentum before equals total signed momentum after. Check kinetic energy separately when deciding whether the collision is elastic.",
        r"colli(?:sion|de)|explosion|explodes|conservation of momentum")
pattern("impulse-force-time", "dynamics", "Link impulse, momentum change and force–time area",
        "Impulse equals change in momentum and the signed area under a force–time graph. For a constant average force, use FΔt = Δp, keeping vector directions consistent.",
        r"\bimpulse\b|force.time|rate of change of momentum")
pattern("terminal-speed", "dynamics", "Explain terminal speed using balanced forces",
        "As speed rises, resistive force rises. Terminal speed occurs when the resultant force and acceleration are zero, even though the object is still moving. Compare forces before and after a change.",
        r"terminal (?:speed|velocity)")
pattern("moments-equilibrium", "forces", "Balance moments about a pivot",
        "Choose a pivot that removes unknown forces. Use force × perpendicular distance, equate clockwise and anticlockwise moments, and use force balance if another equation is needed.",
        r"pivot|principle of moments|moment of (?:a |the )?force|torque|\bcouple\b")
pattern("fluid-pressure", "forces", "Calculate hydrostatic pressure or upthrust",
        "For a fluid at rest use Δp = ρgΔh; pressure depends on vertical depth. Upthrust equals the weight of displaced fluid. Add atmospheric pressure only when absolute pressure is required.",
        r"hydrostatic|upthrust|buoyan|pressure.{0,90}(?:depth|liquid)|(?:depth|liquid).{0,90}pressure")
pattern("energy-conservation", "energy", "Balance kinetic and gravitational potential energy",
        "Write initial energy plus work supplied = final energy plus energy dissipated. Use ½mv² for kinetic energy and mgΔh near Earth’s surface, taking care not to assume mechanical energy is conserved when drag or friction does work.",
        r"kinetic energy", r"gravitational potential|height|falls|falling|raised|work done|conservation")
pattern("power-efficiency", "energy", "Calculate useful power or efficiency",
        "Use power = energy transferred / time, or P = Fv for a force along motion. Efficiency compares useful output with total input, using energy with energy or power with power.",
        r"efficiency|useful power|output power|power output", r"power|energy|work")
pattern("young-modulus", "deformation", "Calculate stress, strain or Young’s modulus",
        "Use stress = force / original cross-sectional area and strain = extension / original length. Young’s modulus is stress / strain in the linear region. Use diameter to calculate area carefully.",
        r"young.s modulus|\bstress\b.{0,80}\bstrain\b|\bstrain\b.{0,80}\bstress\b")
pattern("spring-energy", "deformation", "Find spring stiffness or elastic energy",
        "For a linear spring use F = kx. Elastic energy is the area under the force–extension graph, equal to ½kx² only in the linear region. Check whether the spring stays within its proportional limit.",
        r"spring constant|force constant|force.extension|elastic potential energy|hooke.s law")
pattern("wave-speed", "waves", "Relate wave speed, frequency and wavelength",
        "Use v = fλ and f = 1/T. Read wavelength as a complete spatial cycle, convert prefixes before substitution, and distinguish particle motion from the motion of the wave.",
        r"wavelength", r"speed|velocity|frequency|period")
pattern("wave-phase", "waves", "Compare phase at two positions or times",
        "For a progressive wave, phase difference is 2πΔx/λ or 2πΔt/T. For a stationary wave, particles in one loop are in phase and neighbouring loops are in antiphase.",
        r"phase difference|in phase|antiphase")
pattern("polarisation", "waves", "Identify polarisation or apply Malus’s law",
        "Polarisation restricts oscillations to one plane and therefore demonstrates transverse motion. For already plane-polarised light through an analyser use I = I₀cos²θ; treat unpolarised light through the first ideal polariser separately.",
        r"polaris|polariz|malus")
pattern("standing-wave-nodes", "superposition", "Locate nodes, antinodes and stationary-wave modes",
        "Sketch the allowed pattern with the correct end conditions. Adjacent nodes are λ/2 apart and a node to its nearest antinode is λ/4. Combine the allowed wavelength with v = fλ.",
        r"stationary wave|standing wave|\bantinode|\bnode\b")
pattern("double-slit", "superposition", "Calculate double-slit fringe spacing",
        "For small angles use fringe spacing w = λD/a. Identify the slit separation and screen distance, then compare proportional changes or calculate a wavelength. Check coherence and path difference when explaining the pattern.",
        r"double.slit|slit separation|fringe (?:spacing|separation)|two.slit")
pattern("diffraction-grating", "superposition", "Use the diffraction-grating equation",
        "Convert lines per unit length to slit spacing d, then use d sin θ = nλ. Angles are measured from the central direction; the largest order must satisfy sin θ ≤ 1.",
        r"diffraction grating|grating.{0,30}lines|lines per (?:metre|mm|millimetre)")
pattern("ohmic-resistivity", "electricity", "Relate wire resistance to length and area",
        "Use R = ρL/A and A = πd²/4 for a circular wire. Separate a change in geometry from a change in resistivity; stretching at constant volume changes both length and area.",
        r"resistivity|resistance.{0,80}(?:cross.sectional|diameter|length)|(?:cross.sectional|diameter).{0,80}resistance")
pattern("drift-current", "electricity", "Calculate current from charge carriers and drift speed",
        "Use I = nAqv. Identify carrier number per unit volume, cross-sectional area and charge per carrier, then keep all quantities in SI units. Electron drift is opposite to conventional current.",
        r"drift (?:speed|velocity)|number density.{0,70}(?:electron|carrier)|charge carriers.{0,90}(?:speed|velocity)")
pattern("emf-definition", "electricity", "Interpret emf as energy supplied per unit charge",
        "Emf is energy supplied by a source per unit charge passing through it. Potential difference describes energy transferred per unit charge between two points. Distinguish the complete source from one external component.",
        r"electromotive force|e\.m\.f", r"defin|what is meant|which statement.{0,90}describ|which.{0,60}definition")
pattern("kirchhoff-conservation", "circuits", "Connect Kirchhoff’s laws to conservation laws",
        "At a junction, conservation of charge gives current in = current out. Around a loop, conservation of energy gives sum of emfs = sum of potential drops. Identify which law the statement or diagram represents.",
        r"kirchhoff", r"conserv|which.{0,40}law|demonstrat|state|explain")
pattern("potential-divider", "circuits", "Predict a potential divider’s output",
        "Identify the component across which the output is measured. For two unloaded series resistors, Vout = Vin Rout/(R₁ + R₂). Compare the ratio when a thermistor or LDR changes resistance; account for loading when necessary.",
        r"potential divider|voltage divider")
pattern("internal-resistance", "circuits", "Find emf, terminal voltage or internal resistance",
        "Use terminal voltage V = ε − Ir while a cell supplies current. Combine external and internal resistance to find current. On a terminal-voltage/current graph, intercept is emf and gradient is −r.",
        r"internal resistance|terminal (?:voltage|potential difference)|terminal p\.d")
pattern("resistor-network", "circuits", "Reduce series and parallel resistor networks",
        "Identify which components really share current or potential difference. Add series resistances directly and add reciprocals for parallel branches, working inward from the simplest part of the network.",
        r"resistors?", r"parallel|series", r"combined|combination|total resistance|resistance of the (?:circuit|network)|effective resistance")
pattern("centripetal-force", "circular", "Identify the force providing centripetal acceleration",
        "Draw actual forces and resolve them toward the centre. Set the radial resultant equal to mv²/r or mω²r. Centripetal force is the name for that resultant, not an extra force.",
        r"centripetal|circular (?:motion|path)|moves? in a (?:horizontal |vertical )?circle")
pattern("gravitational-field", "gravitation", "Use inverse-square gravitational field or force",
        "Use g = GM/r² or F = GMm/r², measuring r from the centre of a spherical mass. For more than one mass, add vector fields with directions rather than scalar magnitudes.",
        r"gravitational (?:field strength|force)|newton.s law of gravitation")
pattern("orbital-motion", "gravitation", "Combine gravity with circular orbital motion",
        "Set gravitational force equal to the required radial resultant: GMm/r² = mv²/r. Combine v = 2πr/T to find orbital radius, speed or period. Distinguish orbital radius from height above a surface.",
        r"satellite|geostationary|orbital (?:period|speed|radius)|kepler")
pattern("ideal-gas-equation", "gases", "Apply the ideal-gas equation to a change of state",
        "Use pV = nRT or pV = NkT with absolute temperature and absolute pressure. Identify what is fixed before comparing two states; choose either moles or molecule count consistently.",
        r"ideal gas|gas.{0,60}(?:pressure|volume)|(?:pressure|volume).{0,60}gas",
        exclude=r"brownian|collisions? with|collide.{0,30}wall|pressure.{0,35}(?:caused|produced)")
pattern("molecular-kinetic-energy", "gases", "Relate molecular kinetic energy or rms speed to temperature",
        "Use mean translational kinetic energy = 3kT/2 and ½m⟨c²⟩ = 3kT/2. The rms speed is √⟨c²⟩ and scales as √(T/m), with T in kelvin.",
        r"root.mean.square|r\.m\.s.{0,15}speed|mean.square|mean (?:translational )?kinetic energy")
pattern("thermal-energy", "thermodynamics", "Calculate heating or a change of state",
        "Use Q = mcΔT for a temperature change and Q = mL for a phase change. Build an energy balance including all materials heated and any energy losses; temperature remains fixed during an ideal phase change.",
        r"specific heat|heat capacity|specific latent|latent heat")
pattern("first-law", "thermodynamics", "Use the first law of thermodynamics",
        "State the sign convention before calculating. With work done on the gas taken positive, ΔU = Q + W. Track heat transfer and work separately; work by the gas is the area under a pressure–volume curve.",
        r"first law of thermodynamics|internal energy", r"work|heat|thermal|first law")
pattern("shm-relationships", "oscillations", "Connect SHM displacement, acceleration and period",
        "For simple harmonic motion use a = −ω²x and ω = 2π/T. The minus sign means acceleration is directed toward equilibrium. Velocity is greatest at equilibrium and zero at the turning points.",
        r"simple harmonic|s\.h\.m|\bshm\b")
pattern("resonance-damping", "oscillations", "Explain resonance and the effect of damping",
        "Resonance occurs when driving frequency is close to the natural frequency. Damping transfers energy out of the oscillator, reducing and broadening the resonance peak. Distinguish a driven oscillator from a freely decaying one.",
        r"resonance|damping|damped|driving frequency|forced oscillation")
pattern("electric-field-lines", "electric-fields", "Interpret electric field-line diagrams",
        "Field arrows show the force direction on a positive test charge. Lines leave positive charges and enter negative charges, never cross, and are more closely spaced where the field is stronger.",
        r"electric field", r"diagram|field.line|pattern|draw|sketch")
pattern("electric-potential-field", "electric-fields", "Relate electric field, potential and force",
        "Use F = qE and, for a uniform field, E = V/d. For point charges use inverse-square field and inverse-distance potential, adding fields as vectors and potentials as scalars.",
        r"electric (?:field strength|potential)|coulomb.s law|force.{0,35}(?:point )?charge")
pattern("capacitor-charge-energy", "capacitance", "Calculate capacitor charge or stored energy",
        "Use Q = CV and energy = ½QV = ½CV² = Q²/(2C). Choose the expression matching the known quantities, and identify whether charge or voltage stays fixed when the capacitor changes.",
        r"capacitor|capacitance", r"charge|energy|potential difference|voltage")
pattern("capacitor-discharge", "capacitance", "Use a capacitor’s exponential discharge and time constant",
        "For discharge, Q, V and I decay exponentially with time constant RC. Use X = X₀e^(−t/RC), or determine RC from a graph. At one time constant the remaining fraction is 1/e.",
        r"capacitor|capacitance", r"discharg|time constant|exponential")
pattern("magnetic-force", "magnetism", "Find magnetic force or charged-particle curvature",
        "Use F = BIL sin θ for a wire or F = Bqv sin θ for a moving charge. Find direction with the appropriate hand rule, reverse it for a negative charge, and use Bqv = mv²/r for perpendicular circular motion.",
        r"magnetic (?:field|force)|flux density", r"force|electron|proton|charged particle|wire|conductor")
pattern("induction-lenz", "magnetism", "Apply Faraday’s and Lenz’s laws",
        "Induced emf equals the rate of change of flux linkage. Use Lenz’s law to choose the direction that opposes the change causing it. A constant flux linkage produces no induced emf.",
        r"faraday|lenz|flux linkage|electromagnetic induction|induced (?:emf|e\.m\.f|current)")
pattern("ac-rms", "ac", "Convert peak and rms alternating quantities",
        "For a sinusoidal signal use Irms = Ipeak/√2 and Vrms = Vpeak/√2. Average resistor power is Irms²R; the arithmetic average of a complete sinusoidal current is zero.",
        r"r\.m\.s|root.mean.square", r"current|voltage|potential difference")
pattern("rectification", "ac", "Interpret rectification and capacitor smoothing",
        "Follow diode conduction during each half-cycle. Distinguish half-wave from full-wave output, then use capacitor charging and discharging to explain ripple and the effects of load resistance or capacitance.",
        r"rectif|smoothing")
pattern("photoelectric-equation", "quantum", "Apply the photoelectric energy equation",
        "Use hf = Φ + KEmax and Φ = hf₀. A stopping potential gives KEmax = eVs. Frequency controls maximum electron energy; intensity at fixed frequency mainly controls the emission rate above threshold.",
        r"photoelectric|photoelectron|work function|threshold frequency|stopping (?:potential|voltage)",
        r"frequency|wavelength|energy|work function|stopping|potential|voltage")
pattern("photoelectric-definition", "quantum", "Recognise what the photoelectric effect demonstrates",
        "The photoelectric effect is emission of electrons from a surface when electromagnetic radiation above a threshold frequency is incident. Explain why photons must each supply enough energy to release an electron.",
        r"photoelectric effect", r"what is meant|define|definition|which statement.{0,80}(?:describ|explain)|state what")
pattern("photon-energy-levels", "quantum", "Connect photon energy with wavelength or energy levels",
        "A photon has E = hf = hc/λ. For a transition, use the magnitude of the difference between the two energy levels, convert eV to joules when needed, and distinguish emission from absorption.",
        r"photon|energy levels?|emission spectrum|line spectrum|absorption spectrum", r"wavelength|frequency|transition|energy level")
pattern("de-broglie", "quantum", "Find a particle’s de Broglie wavelength",
        "Use λ = h/p. For a non-relativistic particle, p = mv; for a particle accelerated through a potential difference, combine qV = p²/(2m) with the de Broglie equation.",
        r"de broglie|electron diffraction|matter wave")
pattern("nuclear-equation", "nuclear", "Balance a nuclear decay or reaction equation",
        "Conserve nucleon number and electric charge across the reaction. Use the resulting proton number to identify the daughter nucleus, and include emitted particles such as beta particles or neutrinos as required.",
        r"nuclear (?:equation|reaction)|decay equation|nucleon number|proton number", r"decay|reaction|equation|emits|emitted")
pattern("half-life-decay", "nuclear", "Calculate half-life, activity or exponential decay",
        "Use A = λN, N = N₀e^(−λt), and λ = ln 2 / t½. Subtract background from count rates before using ratios, and use repeated halving when the elapsed time is a whole number of half-lives.",
        r"half.life|decay constant|radioactive decay|background count")
pattern("binding-energy", "nuclear", "Calculate mass defect and nuclear binding energy",
        "Find the difference between the mass of separate nucleons and the bound nucleus, then use ΔE = Δmc². Keep atomic and nuclear masses consistent and divide by nucleon number only when energy per nucleon is requested.",
        r"binding energy|mass defect|mass.energy equivalence")
pattern("quark-composition", "particles", "Identify particles from quark or lepton properties",
        "Add constituent quark charges and use the particle family: baryons contain three quarks, mesons a quark–antiquark pair, and leptons are not made of quarks. Check conserved quantities in a proposed interaction.",
        r"quark|lepton|baryon|meson|hadron")
pattern("ultrasound-echo", "medical", "Use ultrasound echo time or acoustic impedance",
        "For an echo the wave travels to the boundary and back, so depth = speed × time / 2. Acoustic impedance is ρc; compare impedances to determine reflection at a boundary.",
        r"ultrasound|ultrasonic|acoustic impedance")
pattern("xray-attenuation", "medical", "Calculate exponential X-ray attenuation",
        "Use I = I₀e^(−μx). For several layers, multiply transmission fractions or add μx values in the exponent. Compare transmitted intensities when explaining image contrast.",
        r"attenuation|linear absorption|half.value thickness", r"x.ray|intensity|coefficient")
pattern("stellar-radiation", "astronomy", "Infer stellar temperature, luminosity or distance",
        "Use Wien’s displacement law to connect peak wavelength and temperature, L = 4πr²σT⁴ for luminosity, and received intensity L/(4πd²) for distance. Keep stellar radius separate from distance to the observer.",
        r"wien|stefan|luminosity|black.body|standard candle")
pattern("hubble-redshift", "astronomy", "Use redshift and Hubble’s law",
        "For small speeds, z = Δλ/λ ≈ v/c. Use v = H₀d for recession and convert Hubble-constant units consistently. The estimate 1/H₀ gives a characteristic expansion timescale.",
        r"hubble|red.?shift|expanding universe")
pattern("graph-best-fit", "practical", "Find a best-fit gradient and its uncertainty",
        "Use a large triangle on the best-fit line rather than neighbouring data points. Draw the steepest and shallowest acceptable lines allowed by error bars, then use their gradients to estimate the gradient uncertainty.",
        r"line of best fit|worst acceptable|worst.fit|error bars", r"gradient|slope")
pattern("linearise-equation", "practical", "Linearise an equation and interpret gradient or intercept",
        "Rearrange the model into Y = mX + c. Decide exactly which transformed variables to plot, then equate the gradient and intercept to the corresponding constants. For a power law, take logs on both sides.",
        r"gradient|y.intercept|intercept", r"lg |ln |logarithm|expressions? for|in terms of|straight.line graph|linear relationship")
pattern("experiment-improvements", "practical", "Identify experimental limitations and improvements",
        "Link each limitation to a particular measurement and explain how it affects the result. Propose a practical change that reduces that specific error; repeating readings alone does not correct a systematic error.",
        r"sources? of error|limitations?|improvements?", r"experiment|procedure|measurement|method|accuracy")
pattern("experiment-planning", "practical", "Plan an experiment to test a relationship",
        "Identify independent, dependent and controlled variables. Describe how to measure them, obtain a useful range with repeats, analyse a graph to test the proposed relationship, and address relevant safety and uncertainty.",
        r"design (?:an? |the )?experiment|plan (?:an? |the )?experiment|describe an experiment|design a laboratory")

# Additional recurring operations found by inspecting the unassigned queue.
pattern("quantity-number-unit", "units", "Recognise a measurement as a number and a unit",
        "A measurement gives a numerical value with a unit. Distinguish that complete measurement from a unit name alone, a quantity name alone or a dimensionless percentage.",
        r"(?:represents?|example of).{0,65}(?:measurement|physical quantity)|measurement of a physical quantity")
pattern("percentage-uncertainty", "units", "Find the percentage uncertainty of a measurement",
        "Divide the absolute uncertainty by the measured value and multiply by 100. For an instrument, determine the reading uncertainty from its resolution or the stated measurement procedure first.",
        r"percentage uncertainty", r"measur|mass|length|reading|diameter|value|estimate",
        exclude=r"calculated|volume|surface area|product|quotient|equation|formula")
pattern("repeat-measurements", "units", "Explain what repeats and averaging improve",
        "Repeated measurements reveal spread and help detect anomalous readings. Averaging reduces the effect of random errors. Repeats cannot remove a systematic offset or establish accuracy without a reference.",
        r"repeat(?:ed)? (?:measurements|readings)|taking repeat|calculating a mean|average of.{0,30}readings")
pattern("instrument-resolution", "units", "Read an instrument and estimate its resolution",
        "Read the scale divisions or digital resolution, account for a zero error if given, and report a value and uncertainty with consistent decimal places. For an analogue scale, consider the uncertainty in each endpoint reading.",
        r"micrometer|vernier|resolution|scale division|thermometer", r"read|uncertaint|measur|scale")
pattern("motion-graph-shape", "kinematics", "Match a motion description to a graph",
        "Translate direction into the sign of velocity and changes of speed into acceleration. Read the axes before judging a graph: position, velocity and acceleration have different shapes for the same journey.",
        r"graph", r"motion|moves|runs|travels|journey", r"velocity|displacement|speed|acceleration")
pattern("momentum-mass-speed", "dynamics", "Calculate momentum from mass and velocity",
        "Use p = mv with consistent units and a chosen positive direction. Momentum changes if speed or direction changes; for a reversal, subtract signed final and initial values rather than their magnitudes.",
        r"momentum", r"mass|velocity|speed|definition")
pattern("force-equilibrium", "forces", "Balance forces using a force triangle or components",
        "In equilibrium the vector sum of forces is zero. Draw a closed force triangle for three forces, or equate opposing components along two axes. Do not assume every individual force has the same magnitude.",
        r"forces?", r"equilibrium|balanced forces|force triangle")
pattern("density-mass-volume", "forces", "Relate density, mass and volume",
        "Use ρ = m/V and find the relevant volume from the geometry. Convert cubic units carefully, and distinguish the material density from the average density of a hollow or composite object.",
        r"density", r"mass|volume")
pattern("kinetic-energy-mass-speed", "energy", "Relate kinetic energy to mass and speed",
        "Use KE = ½mv². Compare proportional changes carefully: doubling speed quadruples kinetic energy, while doubling mass doubles it at fixed speed. Convert speeds to m/s before substituting.",
        r"kinetic energy", r"mass|speed|velocity",
        exclude=r"photoelectron|photoelectric|gas molecule|mean kinetic|translational|binding energy")
pattern("work-force-distance", "energy", "Calculate work from force and displacement",
        "Work is force times displacement in the force direction: W = Fs cos θ for a constant force. For a varying force, use the area under a force–displacement graph. A force perpendicular to displacement does no work.",
        r"work done|work is done", r"force|distance|displacement")
pattern("power-rate", "energy", "Relate mechanical power to work, time or speed",
        "Use P = W/t, or P = Fv when the force is parallel to velocity. For lifting at steady speed, combine power with the weight and vertical speed. Separate energy transferred from its rate of transfer.",
        r"\bpower\b", r"work|time|speed|velocity|lifting|raises|lifted",
        exclude=r"resistor|current|voltage|capacitor|photoelectric")
pattern("gravitational-energy-height", "energy", "Find the change in gravitational potential energy",
        "In a uniform gravitational field use ΔE = mgΔh. Only the vertical height change matters. A horizontal displacement at constant height does not change gravitational potential energy.",
        r"gravitational potential energy", r"height|horizontal|vertical|raised|lift|fall|displac")
pattern("elastic-plastic", "deformation", "Distinguish elastic and plastic deformation",
        "Elastic deformation is recovered when the force is removed; plastic deformation leaves a permanent change. The elastic limit and limit of proportionality describe different properties and need not coincide.",
        r"elastic deformation|plastic deformation|elastic limit|permanent (?:extension|deformation)")
pattern("electromagnetic-spectrum", "waves", "Order or identify regions of the electromagnetic spectrum",
        "Use the order radio, microwave, infrared, visible, ultraviolet, X-ray, gamma-ray as frequency increases and wavelength decreases. In vacuum all electromagnetic waves have the same speed.",
        r"electromagnetic spectrum|principal regions?|region of.{0,20}wave", r"wavelength|frequency|order|region")
pattern("transverse-longitudinal", "waves", "Distinguish transverse and longitudinal oscillations",
        "Compare particle oscillation with the direction of energy transfer: perpendicular means transverse and parallel means longitudinal. The wave’s travel direction is different from the instantaneous motion of a particle.",
        r"transverse|longitudinal|oscillations?.{0,45}(?:parallel|perpendicular)")
pattern("doppler-frequency", "waves", "Predict or calculate a Doppler frequency change",
        "Approach compresses arriving wavefronts and raises observed frequency; recession lowers it. Distinguish source speed from observer speed, choose the appropriate Doppler expression, and check the direction before using signs.",
        r"doppler|frequency", r"doppler|observer|observed|heard", r"doppler|moving|moves|swung|speed|approach|reced|motion")
pattern("wave-intensity", "waves", "Relate wave intensity to amplitude or distance",
        "Intensity is proportional to amplitude squared. For a point source radiating uniformly without absorption, it varies as 1/r². Distinguish a change in wave amplitude from a change in source power.",
        r"intensity", r"amplitude|point source|distance|inverse.square",
        exclude=r"x.ray|attenuat|electric field|photoelectric")
pattern("diffraction-gap", "superposition", "Compare diffraction at a gap or obstacle",
        "Diffraction is more pronounced when wavelength is comparable to, or larger than, the gap size. Compare the ratio of wavelength to aperture width rather than considering either alone.",
        r"diffract", r"gap|obstacle|aperture|single slit",
        exclude=r"grating")
pattern("electrical-power-energy", "electricity", "Use electrical power and energy relations",
        "Use P = VI = I²R = V²/R for an ohmic resistor, and E = Pt or E = QV for transferred energy. Choose the relation matching what is known and distinguish power from energy.",
        r"power|energy dissipat|energy transfer|energy supplied", r"resistor|current|potential difference|voltage|charge|kettle",
        exclude=r"photoelectric|capacitor|binding|gravitational")
pattern("charge-current-time", "electricity", "Relate current to charge flowing per unit time",
        "Use I = ΔQ/Δt for constant or average current. Charge is the area under a current–time graph. Conventional current follows positive-charge flow, opposite to the drift of electrons in a metal.",
        r"current|charge flow", r"charge", r"time|per second|rate of flow|rate of charge",
        exclude=r"capacitor|drift speed|drift velocity")
pattern("current-voltage-curve", "electricity", "Interpret current–voltage characteristics",
        "Read which quantity is on each axis. An ohmic resistor at constant temperature has a straight I–V line through the origin; a filament lamp heats up and changes resistance; a diode conducts mainly in one direction. Use V/I for resistance at a point.",
        r"current.voltage|i.?v.{0,20}characteristic|characteristic.{0,30}(?:lamp|diode)|(?:lamp|diode).{0,30}characteristic")
pattern("rutherford-scattering", "particles", "Infer atomic structure from alpha-particle scattering",
        "Most particles passing through shows that most of the atom is empty space. Rare large deflections indicate a small, massive, positively charged nucleus. Separate conclusions supported by scattering from facts requiring other evidence.",
        r"rutherford|particle scattering|gold foil")
pattern("decay-emitted-particles", "nuclear", "Identify particles emitted in nuclear decay",
        "Use changes in nucleon number and charge to identify alpha, beta or gamma emission. For beta decay, also use lepton-number conservation to distinguish a neutrino from an antineutrino.",
        r"decay|emits|emitted", r"nucleus|nuclei|beta|alpha|positron|neutrino")
pattern("fundamental-particles", "particles", "Distinguish fundamental and composite particles",
        "Quarks and leptons are fundamental in the standard model. Protons and neutrons are composite hadrons made of quarks. Antiparticles can be fundamental too; being electrically neutral does not decide the classification.",
        r"fundamental particle|elementary particle")
pattern("opamp-gain", "electronics", "Calculate an operational amplifier’s voltage gain",
        "Identify inverting or non-inverting negative feedback, then use the corresponding resistor-ratio gain. Check the output against the supply rails, since a calculated output beyond a rail is clipped by saturation.",
        r"operational amplifier|op.amp|inverting amplifier", r"gain|resistan|voltage|output")
pattern("logic-truth-table", "electronics", "Build a logic-gate truth table",
        "Evaluate each gate in signal order for every input combination. An inversion changes 0 to 1 and 1 to 0. Keep intermediate outputs labelled when gates are combined.",
        r"logic gate|truth table|\bnand\b|\bnor gate|\band gate|\bor gate")
pattern("modulation-sidebands", "communications", "Relate modulation, carrier frequency and sidebands",
        "For amplitude modulation, sidebands occur at carrier frequency plus and minus the signal frequency. Identify whether amplitude or frequency carries the information and relate signal bandwidth to the frequency range being transmitted.",
        r"modulation|sideband|carrier frequency|carrier wave")
pattern("sampling-digital", "communications", "Interpret sampling and analogue-to-digital conversion",
        "Separate sampling rate from bit depth. The rate sets how often a value is measured; bit depth sets the number of available levels. A signal must be sampled above twice its highest frequency to avoid aliasing.",
        r"analogue.to.digital|sampling frequency|sampling rate|digital.to.analogue|number of bits")
pattern("temperature-conversion", "temperature", "Convert Celsius and thermodynamic temperatures",
        "Use T/K = θ/°C + 273.15 (or 273 at the precision requested). A temperature difference has the same numerical value in kelvin and Celsius; a temperature ratio must use kelvin.",
        r"celsius|kelvin|thermodynamic temperature|absolute zero", r"convert|scale|temperature|absolute zero")
pattern("brownian-motion", "gases", "Explain the evidence from Brownian motion",
        "Visible smoke or pollen particles move randomly because of uneven collisions with much smaller molecules. The visible particles are not the molecules themselves. Relate the observations only to conclusions they support.",
        r"brownian|smoke particles|pollen grains")
pattern("boiling-evaporation", "thermodynamics", "Distinguish boiling, evaporation and evaporative cooling",
        "Evaporation happens at a surface over a range of temperatures; boiling occurs throughout a liquid at its boiling point for the given pressure. Evaporation preferentially removes higher-energy molecules and can cool the remaining liquid.",
        r"boiling|evaporation|evaporat", r"surface|cool|molecules|difference|statement|explain")

TYPE_IDS = {item["id"] for item in TYPES}
BY_ID = {item["id"]: item for item in TYPES}
PUBLIC_TYPES = [{key: value for key, value in item.items() if key not in ("requirements", "exclude")}
                for item in TYPES]
PUBLIC_TYPES.sort(key=lambda item: next(index for index, topic in enumerate(TOPICS) if topic["id"] == item["topic"]))
COMPILED = [(item["id"], [re.compile(rule, re.I) for rule in item["requirements"]],
             re.compile(item["exclude"], re.I) if item["exclude"] else None) for item in TYPES]


def stem(text, component):
    """Keep distractors out of pattern classification where labels are readable."""
    if component == "1":
        # Locate the tightest ordered A/B/C/D block in linear-size label lists.
        # Nested greedy lookaheads can take minutes on long scanned questions.
        # A diagram point or variable A preceding the choices is not the start.
        lines = text.splitlines()
        positions = {label: [] for label in "ABCD"}
        for index, line in enumerate(lines):
            match = re.match(r"^([ABCD])(?:\s|$)", line.strip())
            if match:
                positions[match[1]].append(index)
        candidates = []
        for last in positions["D"]:
            sequence = [last]
            for label in "CBA":
                index = bisect_left(positions[label], sequence[0]) - 1
                if index < 0:
                    break
                sequence.insert(0, positions[label][index])
            if len(sequence) == 4 and sequence[0] > 0:
                candidates.append(sequence)
        if candidates:
            first = min(candidates, key=lambda sequence: sequence[-1] - sequence[0])[0]
            text = "\n".join(lines[:first])
    text = re.sub(r"\s+", " ", text).lower()
    # A boilerplate assumption is not evidence of an internal-resistance task.
    text = re.sub(r"(?<!non-)(?<!non )\b(?:negligible|zero|no) internal resistance", "", text)
    text = re.sub(r"internal resistance (?:is |of )?(?:negligible|zero)", "", text)
    return text


def classify_types(text, component=None):
    text = stem(text, component)
    matches = []
    for key, requirements, exclusion in COMPILED:
        found = [rule.search(text) for rule in requirements]
        if all(found) and not (exclusion and exclusion.search(text)):
            matches.append((key, list(dict.fromkeys(match.group(0) for match in found))))
    if component == "1":
        # A numerical context does not determine the operation being tested.
        # E.g. units of a heat-capacity constant is dimensional analysis, and
        # uncertainty in a resistance is uncertainty propagation, not circuits.
        dimensional = {"si-base-quantity", "si-base-unit", "derive-base-units",
                       "dimensional-consistency", "compare-units", "unit-prefix"}
        uncertainty = {"uncertainty-propagation", "uncertainty-conversion"}
        uncertainty.add("percentage-uncertainty")
        for family in (dimensional, uncertainty, {"emf-definition"}, {"photoelectric-definition"}):
            if any(key in family for key, _ in matches):
                return [(key, evidence) for key, evidence in matches if key in family]
    return matches


def build_type_index(db):
    """Rebuild only derived assignments; learner corrections live elsewhere."""
    db.executescript("""CREATE TABLE IF NOT EXISTS task_type_suggestions (
        task_id TEXT NOT NULL, type_id TEXT NOT NULL, evidence TEXT NOT NULL,
        PRIMARY KEY(task_id,type_id));
        CREATE INDEX IF NOT EXISTS suggestions_by_type ON task_type_suggestions(type_id,task_id);
        DELETE FROM task_type_suggestions;""")
    import json
    rows = db.execute("SELECT t.id,t.text,d.component FROM tasks t JOIN documents d ON d.id=t.document_id").fetchall()
    for key, text, component in rows:
        db.executemany("INSERT INTO task_type_suggestions VALUES(?,?,?)",
                       [(key, type_id, json.dumps(evidence)) for type_id, evidence in classify_types(text, component)])
    db.execute("INSERT OR REPLACE INTO metadata VALUES('type_rules_version',?)", (VERSION,))
    return db.execute("SELECT COUNT(DISTINCT task_id),COUNT(*) FROM task_type_suggestions").fetchone()
