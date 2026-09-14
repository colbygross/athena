import React, { useState, useEffect } from 'react';

// Full 7-Day Kickboxing & Weightlifting Split derived directly from Workout_Routine.pdf
const weeklySplit = [
  {
    dayName: "Monday",
    title: "Upper Body Strength & LISS Cardio / Core",
    amSession: {
      name: "Primary AM: Upper Body Strength (60 Mins)",
      goal: "Heavy compound loading. Rest 90–120s between heavy sets.",
      activity: "lift",
      duration: 60,
      intensity: "high",
      calories: 520,
      sections: [
        {
          name: "1. Warm-up & Shoulder Prep (8 Mins)",
          exercises: [
            "3 mins light treadmill walk or jump rope",
            "Band Face-Pulls: 2 sets x 15 reps",
            "Arm Circles & Cat-Cow stretches: 2 sets x 10 reps"
          ]
        },
        {
          name: "2. Compound Push & Pull (24 Mins)",
          exercises: [
            "Barbell Bench Press: 3 sets x 6–8 reps (2 RIR — leave 2 reps in tank)",
            "Barbell or Pendlay Rows: 3 sets x 6–8 reps (Torso parallel to ground)"
          ]
        },
        {
          name: "3. Vertical Press & Pull (20 Mins)",
          exercises: [
            "Overhead Barbell Press (OHP): 3 sets x 8 reps (Strict form, no leg drive)",
            "Neutral-Grip Pull-ups or Lat Pulldowns: 3 sets x 8–10 reps"
          ]
        },
        {
          name: "4. Finisher Superset (8 Mins)",
          exercises: [
            "Incline Dumbbell Flyes: 2 sets x 12–15 reps",
            "Superset with Cable Face Pulls: 2 sets x 15 reps (Rear delts & shoulder health)"
          ]
        }
      ]
    },
    pmSession: {
      name: "Secondary PM: LISS Cardio & Core (60 Mins)",
      goal: "Flush upper body soreness without fatiguing legs for Wednesday.",
      activity: "cardio",
      duration: 60,
      intensity: "medium",
      calories: 380,
      sections: [
        {
          name: "1. Zone 2 Incline Treadmill Walk (40 Mins)",
          exercises: [
            "Treadmill Incline: 8–10%, Speed: 2.8–3.2 mph",
            "Heart Rate: Conversational pace (~120–130 bpm)"
          ]
        },
        {
          name: "2. Core Circuit (15 Mins - 3 Rounds)",
          exercises: [
            "Plank Hold: 60 seconds",
            "Hanging Leg Raises: 12 reps",
            "Ab Wheel Rollouts or RKC Planks: 10 reps (Rest 60s between rounds)"
          ]
        },
        {
          name: "3. Cool-down (5 Mins)",
          exercises: [
            "Static lat and chest stretching against rack"
          ]
        }
      ]
    }
  },
  {
    dayName: "Tuesday",
    title: "Kickboxing & Joint Prehab / Soft Tissue",
    amSession: {
      name: "Primary AM: Kickboxing & High-Intensity Conditioning (60 Mins)",
      goal: "High-output striking, footwork, and conditioning.",
      activity: "kickboxing",
      duration: 60,
      intensity: "high",
      calories: 650,
      sections: [
        {
          name: "1. Dynamic Warm-up & Shadowboxing (10 Mins)",
          exercises: [
            "3 mins Jump Rope",
            "Dynamic hips / leg swings",
            "Shadowboxing: 2 rounds x 3 mins (1-2s, slips, low kicks)"
          ]
        },
        {
          name: "2. Heavy Bag Work (24 Mins — 6 Rounds x 3 Mins, 1 Min Rest)",
          exercises: [
            "Round 1: Jab-Cross-Lead Hook (1-2-3) + Lead Low Kick",
            "Round 2: Cross-Hook-Cross (2-3-2) + Rear Heavy Low Kick",
            "Round 3: Inside Leg Kick + Jab-Cross + Rear Body Kick",
            "Round 4: Pressure Round (Punches in bunches, 1-2-1-2s high HR)",
            "Round 5: Counter-Striking (Slip left, left hook, rear kick)",
            "Round 6: Freestyle Flow (Punches, knees, kicks at 80% power)"
          ]
        },
        {
          name: "3. Bodyweight HIIT Conditioning (15 Mins - 3 Rounds, 45s work / 15s rest)",
          exercises: [
            "Kettlebell Swings",
            "Burpees (No push-up to save shoulders)",
            "Plyo Lunges or Speed Skaters",
            "Mountain Climbers"
          ]
        },
        {
          name: "4. Cool-Down & Heart Rate Drop (11 Mins)",
          exercises: [
            "Slow walking, deep diaphragmatic breathing, calf/hip flexor holds"
          ]
        }
      ]
    },
    pmSession: {
      name: "Secondary PM: Joint Prehab & Soft Tissue (60 Mins)",
      goal: "Prepare lower body joints for Wednesday's heavy squats.",
      activity: "recovery",
      duration: 60,
      intensity: "low",
      calories: 180,
      sections: [
        {
          name: "1. Foam Rolling & Trigger Point (20 Mins)",
          exercises: [
            "4 mins per area: Calves/Achilles, IT Bands/Quads, Glutes/Piriformis, Lats"
          ]
        },
        {
          name: "2. Ankle & Tibialis Prehab (15 Mins)",
          exercises: [
            "Weighted Tibialis Raises: 3 sets x 20 reps (Shin strength for striking)",
            "Soleus Wall Stretches: 3 sets x 45-second holds per leg"
          ]
        },
        {
          name: "3. Active Mobility (20 Mins)",
          exercises: [
            "90/90 Hip Switches: 2 sets x 10 reps per side",
            "Cossack Squats: 3 sets x 8 reps per side (Unloaded groin/hip opener)",
            "World's Greatest Stretch: 5 slow reps per side"
          ]
        }
      ]
    }
  },
  {
    dayName: "Wednesday",
    title: "Lower Body Squat Focus & Shadowboxing Flush",
    amSession: {
      name: "Primary AM: Lower Body A — Squat Focus (60 Mins)",
      goal: "Quad hypertrophy and heavy leg strength. Rest 2–3 mins on main lifts.",
      activity: "lift",
      duration: 60,
      intensity: "high",
      calories: 550,
      sections: [
        {
          name: "1. Warm-up & Ankle/Hip Prep (10 Mins)",
          exercises: [
            "3 mins light bike ride",
            "Goblet Squats: 2 sets x 10 reps (Hold 3s at bottom)",
            "Glute Bridges + Ankle Mobility Circles: 2 sets x 12 reps"
          ]
        },
        {
          name: "2. Compound Quad & Hinge Strength (27 Mins)",
          exercises: [
            "Barbell Back Squats: 3 sets x 6–8 reps (Focus on depth, leave 2 RIR)",
            "Romanian Deadlifts (RDLs): 3 sets x 8–10 reps (Hamstring/glute stretch)"
          ]
        },
        {
          name: "3. Quad Mass & Finishers (18 Mins)",
          exercises: [
            "Leg Press or Hack Squat: 3 sets x 10–12 reps (60-90s rest, deep stretch)",
            "Seated Calf Raises: 3 sets x 15 reps (Pause 1s at peak)",
            "Superset with Lying Leg Curls: 3 sets x 12 reps"
          ]
        }
      ]
    },
    pmSession: {
      name: "Secondary PM: Technical Shadowboxing & Light Flush (60 Mins)",
      goal: "Promote lower body blood flow and refine striking technique without impact.",
      activity: "cardio",
      duration: 60,
      intensity: "low",
      calories: 250,
      sections: [
        {
          name: "1. Zone 1 Spin Bike (25 Mins)",
          exercises: [
            "Light resistance at comfortable cadence (~80–90 RPM) to flush squat fatigue"
          ]
        },
        {
          name: "2. Mirror Shadowboxing — Hands & Head Movement (20 Mins)",
          exercises: [
            "Rule: Feet planted, NO kicks or explosive jumps",
            "Jab-cross-hook combos, slipping punches, lead foot pivots"
          ]
        },
        {
          name: "3. Cool-Down Mobility (15 Mins)",
          exercises: [
            "Hip flexor lengtheners to undo squat tightness"
          ]
        }
      ]
    }
  },
  {
    dayName: "Thursday",
    title: "Mid-Week Active Recovery & Full CNS Rest",
    amSession: {
      name: "Primary AM: Active Recovery & Outdoor Walk (60 Mins)",
      goal: "Low-intensity movement, mental reset, and cardiovascular recovery.",
      activity: "recovery",
      duration: 60,
      intensity: "low",
      calories: 220,
      sections: [
        {
          name: "1. Outdoor Power Walk (45 Mins)",
          exercises: [
            "Brisk walk outdoors at ~3.2–3.8 mph for sunlight & circadian reset"
          ]
        },
        {
          name: "2. Decompression Stretch (15 Mins)",
          exercises: [
            "Cat-Cow / Thoracic Rotations: 2 sets x 10 reps",
            "Child's Pose to Cobra: Hold 45s x 3 rounds",
            "Doorway Chest Stretch: Hold 60s per side"
          ]
        }
      ]
    },
    pmSession: {
      name: "Secondary PM: Complete Rest & CNS Recharge",
      goal: "Fully off. Rest, hydrate, eat quality protein, and let neuromuscular system adapt.",
      activity: "recovery",
      duration: 0,
      intensity: "low",
      calories: 0,
      sections: [
        {
          name: "Full Rest Day / OFF",
          exercises: [
            "No gym, no cardio. Eat quality protein and hydrate."
          ]
        }
      ]
    }
  },
  {
    dayName: "Friday",
    title: "Upper Body Hypertrophy & Hands-Only Boxing Bag Work",
    amSession: {
      name: "Primary AM: Upper Body B — Hypertrophy Focus (60 Mins)",
      goal: "Higher rep ranges (10–12 reps), shorter rest (60–90s), and pump.",
      activity: "lift",
      duration: 60,
      intensity: "high",
      calories: 490,
      sections: [
        {
          name: "1. Warm-up & Shoulder Mobility (8 Mins)",
          exercises: [
            "3 mins light treadmill walk",
            "Band Pull-Aparts: 2 sets x 15 reps",
            "Scapular Push-ups: 2 sets x 10 reps"
          ]
        },
        {
          name: "2. Upper Chest & Back Density (24 Mins)",
          exercises: [
            "Incline Dumbbell Press: 3 sets x 10–12 reps (Squeeze top, 2s negative)",
            "Seated Cable Rows (Neutral/Wide Grip): 3 sets x 10–12 reps (1s peak hold)"
          ]
        },
        {
          name: "3. Delts & Arms Superset (20 Mins)",
          exercises: [
            "Dumbbell Lateral Raises: 4 sets x 12–15 reps",
            "Incline DB Bicep Curls: 3 sets x 12 reps",
            "Superset with Overhead Rope Tricep Extensions: 3 sets x 12 reps"
          ]
        },
        {
          name: "4. Chest & Upper Back Finisher (8 Mins)",
          exercises: [
            "Push-ups: 2 sets to near-failure",
            "Superset with Straight-Arm Cable Pushdowns: 2 sets x 15 reps"
          ]
        }
      ]
    },
    pmSession: {
      name: "Secondary PM: Hands-Only Boxing Bag Work & Core (60 Mins)",
      goal: "High-volume striking conditioning without fatiguing legs for Saturday.",
      activity: "kickboxing",
      duration: 60,
      intensity: "high",
      calories: 550,
      sections: [
        {
          name: "1. Warm-up (10 Mins)",
          exercises: [
            "Jump rope and shoulder dislocates with resistance band"
          ]
        },
        {
          name: "2. Boxing Bag Rounds (24 Mins — 6 Rounds x 3 Mins, 1 Min Rest, NO KICKS)",
          exercises: [
            "Round 1: Jab-Cross-Jab (1-2-1) + Step-and-pivot footwork",
            "Round 2: Body-head combinations (Double jab high, cross body, hook high)",
            "Round 3: Inside fighting (Short hooks and uppercuts at close range)",
            "Round 4: Speed Round (10s non-stop 1-2 bursts / 10s light footwork)",
            "Round 5: Slip and Counter (Slip right, cross-hook-cross)",
            "Round 6: Freestyle Flow (Controlled pace, crisp technique)"
          ]
        },
        {
          name: "3. Rotational Core Work (15 Mins - 3 Rounds)",
          exercises: [
            "Russian Twists: 20 reps (10 per side)",
            "Cable Woodchoppers: 12 reps per side",
            "Pallof Press: 10 holds (3s pause per side)"
          ]
        },
        {
          name: "4. Cool-down (11 Mins)",
          exercises: [
            "Light chest stretching and wrist/forearm rolls"
          ]
        }
      ]
    }
  },
  {
    dayName: "Saturday",
    title: "Lower Body Hinge / Athletic Focus & Leisure",
    amSession: {
      name: "Primary AM: Lower Body B — Hinge & Athletic Focus (60 Mins)",
      goal: "Unilateral strength, hamstring power, and glute activation.",
      activity: "lift",
      duration: 60,
      intensity: "high",
      calories: 530,
      sections: [
        {
          name: "1. Dynamic Warm-up & Glute Activation (10 Mins)",
          exercises: [
            "3 mins stationary bike",
            "Lateral Band Walks: 2 sets x 12 reps",
            "Bodyweight Reverse Lunges: 2 sets x 10 reps"
          ]
        },
        {
          name: "2. Unilateral Quad/Glute & Hamstring Mass (27 Mins)",
          exercises: [
            "Bulgarian Split Squats: 3 sets x 8–10 reps per leg",
            "Dumbbell or Barbell Stiff-Legged Deadlift: 3 sets x 10 reps (Deep stretch)"
          ]
        },
        {
          name: "3. Posterior Chain & Calves/Adductors (23 Mins)",
          exercises: [
            "Lying or Seated Leg Curls: 3 sets x 12–15 reps (3s eccentric phase)",
            "Standing Calf Raises: 4 sets x 12 reps (Pause at top)",
            "Copenhagen Planks (Adductor hold): 3 sets x 20–30s per side"
          ]
        }
      ]
    },
    pmSession: {
      name: "Secondary PM: Active Recovery / Outdoor Recreation",
      goal: "Enjoy your weekend. Casual walk, cycling, or swimming. Let body repair.",
      activity: "recovery",
      duration: 30,
      intensity: "low",
      calories: 150,
      sections: [
        {
          name: "Leisure Outdoor Activity / Rest",
          exercises: [
            "Casual outdoor walk, leisure cycling, or full rest ahead of Sunday Yoga."
          ]
        }
      ]
    }
  },
  {
    dayName: "Sunday",
    title: "Sunday Athlete Recovery Flow (Yoga & Deep Mobility)",
    amSession: {
      name: "Primary (AM or PM): 60-Minute Sunday Athlete Recovery Flow",
      goal: "Spinal decompression, hip/ankle openers, and nervous system down-regulation.",
      activity: "yoga",
      duration: 60,
      intensity: "low",
      calories: 200,
      sections: [
        {
          name: "Phase 1: Spinal Decompression & Breath Alignment (10 Mins)",
          exercises: [
            "Child's Pose with Lat Reach: 3 mins (90s per side)",
            "Cat-Cow to Thread the Needle: 4 mins (10 Cat-Cows + 90s per side thread needle)",
            "Downward Dog Heel Pedals: 3 mins (Open tight calves & Achilles)"
          ]
        },
        {
          name: "Phase 2: Dynamic Hip & Ankle Opener (15 Mins)",
          exercises: [
            "World's Greatest Stretch w/ T-Spine Reach: 5 slow reps/side (hold lunges 5s)",
            "Low Lunge to Half Splits Flow: 5 mins (10 dynamic transitions/leg)",
            "Garland Pose / Deep Squat Hold: 5 mins (Shift weight side-to-side)"
          ]
        },
        {
          name: "Phase 3: Deep Yin Holds (25 Mins)",
          exercises: [
            "Pigeon Pose: 3 mins per side (Gluteus medius & outer hip)",
            "Frog Pose: 4 mins (Adductor/groin stretch)",
            "Lying Hero Pose or Supine Quad Stretch: 4 mins",
            "Puppy Pose / Melting Heart: 3 mins (Unlocks chest & t-spine)",
            "Reclined Spinal Twist: 4 mins (2 mins per side for lumbar spine)"
          ]
        },
        {
          name: "Phase 4: Parasympathetic Down-Regulation (10 Mins)",
          exercises: [
            "Legs-Up-The-Wall Pose (Savasana): 10 mins (4s inhale / 6s exhale)"
          ]
        }
      ]
    },
    pmSession: {
      name: "Secondary PM: Complete Rest",
      goal: "Rest and recover for Monday's Upper Body Strength session.",
      activity: "recovery",
      duration: 0,
      intensity: "low",
      calories: 0,
      sections: [
        {
          name: "Full Rest",
          exercises: ["Complete rest."]
        }
      ]
    }
  }
];

const getDayOfWeekIndex = () => {
  const day = new Date().getDay(); // 0 is Sunday, 1 is Monday...
  return day === 0 ? 6 : day - 1; // Map Monday=0, Tuesday=1 ... Sunday=6
};

function FitnessTab({
  fitnessData,
  healthData,
  mealsData,
  mindfulnessData,
  handleFormSubmit,
  fetchAllData,
  showToast,
  API_BASE,
  renderRelatedAreas
}) {
  const [healthSubTab, setHealthSubTab] = useState('split');
  const [selectedDayIdx, setSelectedDayIdx] = useState(() => getDayOfWeekIndex());
  
  const [checkedExercises, setCheckedExercises] = useState(() => {
    try {
      const saved = localStorage.getItem('athena-kickboxing-split-checks');
      return saved ? JSON.parse(saved) : {};
    } catch (e) {
      return {};
    }
  });

  const [fitForm, setFitForm] = useState({
    date: new Date().toISOString().split('T')[0],
    activity_type: 'lift',
    duration_minutes: '60',
    distance_km: '',
    calories_burned: '500',
    intensity: 'high',
    notes: ''
  });

  const [healthForm, setHealthForm] = useState({
    date: new Date().toISOString().split('T')[0],
    weight_lbs: '',
    sleep_hours: '',
    mood: '8',
    systolic: '',
    diastolic: '',
    notes: '',
    water_ml: '3785', // 1 Gallon = 3785ml
    energy_level: '8',
    stress_level: '3'
  });

  const [mealForm, setMealForm] = useState({
    date: new Date().toISOString().split('T')[0],
    meal_type: 'breakfast',
    description: '',
    calories: '',
    protein_g: '',
    carbs_g: '',
    fat_g: ''
  });

  const [mindForm, setMindForm] = useState({
    date: new Date().toISOString().split('T')[0],
    activity_type: 'yoga',
    duration_minutes: '60',
    notes: 'Sunday Athlete Recovery Flow (Yin Holds & Breathwork)'
  });

  useEffect(() => {
    localStorage.setItem('athena-kickboxing-split-checks', JSON.stringify(checkedExercises));
  }, [checkedExercises]);

  const handleExerciseCheck = (dayIdx, sessionType, exKey, val) => {
    setCheckedExercises(prev => ({
      ...prev,
      [`${dayIdx}-${sessionType}-${exKey}`]: val
    }));
  };

  const handleLogSession = async (dayIdx, sessionType) => {
    const day = weeklySplit[dayIdx];
    const session = sessionType === 'am' ? day.amSession : day.pmSession;
    if (!session || session.duration === 0) return;

    let exercisesText = [];
    session.sections.forEach((sec, sIdx) => {
      sec.exercises.forEach((ex, eIdx) => {
        if (checkedExercises[`${dayIdx}-${sessionType}-${sIdx}-${eIdx}`]) {
          exercisesText.push(ex);
        }
      });
    });

    const notesStr = `[Workout_Routine.pdf] ${session.name}. ` +
      (exercisesText.length > 0 ? `Completed: ${exercisesText.join(' | ')}.` : `Goal: ${session.goal}`);

    const payload = {
      date: fitForm.date || new Date().toISOString().split('T')[0],
      activity_type: session.activity,
      duration_minutes: session.duration,
      distance_km: null,
      calories_burned: session.calories,
      intensity: session.intensity,
      notes: notesStr
    };

    try {
      const res = await fetch(`${API_BASE}/fitness`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).then(r => r.json());
      
      if (res.status === 'success') {
        showToast(`Logged ${session.name} to Athena!`, "success");
        fetchAllData();
      }
    } catch (err) {
      showToast("Error logging session: " + err, "error");
    }
  };

  const currentDay = weeklySplit[selectedDayIdx];
  const todayIdx = getDayOfWeekIndex();

  if (!fitnessData || !healthData || !mealsData || !mindfulnessData) return null;

  return (
    <div>
      <header className="page-header" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 className="page-title text-gradient-green glitch-text">Fitness & Health</h1>
            <p className="page-subtitle font-mono">Athena Athletic Program</p>
          </div>
          <div style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--accent-green)' }}>
            <span>TODAY: {weeklySplit[todayIdx].dayName.toUpperCase()}</span>
          </div>
        </div>
      </header>

      {/* Sub Tabs Navigation */}
      <div className="health-subtab-bar" style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', borderBottom: '1px solid var(--border-glass)', paddingBottom: '0.5rem' }}>
        <button 
          className={`health-subtab-btn font-mono ${healthSubTab === 'split' ? 'active' : ''}`}
          onClick={() => setHealthSubTab('split')}
          style={{ padding: '0.5rem 1rem', background: healthSubTab === 'split' ? 'rgba(0, 255, 150, 0.1)' : 'transparent', border: 'none', borderBottom: healthSubTab === 'split' ? '2px solid var(--accent-green)' : 'none', color: healthSubTab === 'split' ? 'var(--accent-green)' : 'var(--text-muted)', cursor: 'pointer' }}
        >
          ⚡ DUAL_SESSION_SPLIT
        </button>
        <button 
          className={`health-subtab-btn font-mono ${healthSubTab === 'overload' ? 'active' : ''}`}
          onClick={() => setHealthSubTab('overload')}
          style={{ padding: '0.5rem 1rem', background: healthSubTab === 'overload' ? 'rgba(0, 240, 255, 0.1)' : 'transparent', border: 'none', borderBottom: healthSubTab === 'overload' ? '2px solid var(--accent-cyan)' : 'none', color: healthSubTab === 'overload' ? 'var(--accent-cyan)' : 'var(--text-muted)', cursor: 'pointer' }}
        >
          📈 PROGRESSIVE_OVERLOAD
        </button>
        <button 
          className={`health-subtab-btn font-mono ${healthSubTab === 'nutrition' ? 'active' : ''}`}
          onClick={() => setHealthSubTab('nutrition')}
          style={{ padding: '0.5rem 1rem', background: healthSubTab === 'nutrition' ? 'rgba(255, 186, 0, 0.1)' : 'transparent', border: 'none', borderBottom: healthSubTab === 'nutrition' ? '2px solid var(--accent-yellow)' : 'none', color: healthSubTab === 'nutrition' ? 'var(--accent-yellow)' : 'var(--text-muted)', cursor: 'pointer' }}
        >
          🥗 FUELING_&_MACROS
        </button>
        <button 
          className={`health-subtab-btn font-mono ${healthSubTab === 'biometrics' ? 'active' : ''}`}
          onClick={() => setHealthSubTab('biometrics')}
          style={{ padding: '0.5rem 1rem', background: healthSubTab === 'biometrics' ? 'rgba(188, 19, 254, 0.1)' : 'transparent', border: 'none', borderBottom: healthSubTab === 'biometrics' ? '2px solid var(--accent-purple)' : 'none', color: healthSubTab === 'biometrics' ? 'var(--accent-purple)' : 'var(--text-muted)', cursor: 'pointer' }}
        >
          🧘 RECOVERY_&_BIOMETRICS
        </button>
      </div>

      {/* SUBTAB 1: DUAL SESSION SPLIT */}
      {healthSubTab === 'split' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Day Selector Buttons */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '0.5rem' }}>
            {weeklySplit.map((day, idx) => {
              const isToday = idx === todayIdx;
              const isSelected = idx === selectedDayIdx;
              return (
                <button
                  key={idx}
                  onClick={() => setSelectedDayIdx(idx)}
                  className={`btn-secondary ${isSelected ? 'active' : ''}`}
                  style={{
                    padding: '0.6rem 0.3rem',
                    fontSize: '0.75rem',
                    fontFamily: 'var(--font-mono)',
                    border: isSelected ? '2px solid var(--accent-green)' : isToday ? '1px solid var(--accent-yellow)' : '1px solid var(--border-glass)',
                    background: isSelected ? 'rgba(0, 255, 150, 0.15)' : 'rgba(0,0,0,0.2)',
                    color: isSelected ? 'var(--accent-green)' : isToday ? 'var(--accent-yellow)' : 'var(--text-primary)',
                    cursor: 'pointer',
                    position: 'relative'
                  }}
                >
                  <div style={{ fontWeight: 'bold' }}>{day.dayName.substring(0, 3).toUpperCase()}</div>
                  <div style={{ fontSize: '0.6rem', opacity: 0.8, marginTop: '0.2rem' }}>
                    {idx === 0 ? "Upper A" : idx === 1 ? "Kickbox" : idx === 2 ? "Lower A" : idx === 3 ? "Rest" : idx === 4 ? "Upper B" : idx === 5 ? "Lower B" : "Yoga"}
                  </div>
                  {isToday && (
                    <span style={{ position: 'absolute', top: '4px', right: '4px', width: '6px', height: '6px', background: 'var(--accent-yellow)', borderRadius: '50%' }} />
                  )}
                </button>
              );
            })}
          </div>

          {/* Selected Day Header */}
          <div className="glass-panel" style={{ padding: '1rem', borderLeft: '4px solid var(--accent-green)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 className="panel-title" style={{ fontSize: '1.2rem', color: 'var(--accent-green)' }}>{currentDay.dayName}: {currentDay.title}</h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '0.2rem 0 0 0' }}>
                  Structure: AM Non-Negotiable Anchor + PM Complementary Session (Low-CNS)
                </p>
              </div>
              <span className="badge badge-success" style={{ fontFamily: 'monospace' }}>
                {selectedDayIdx === todayIdx ? "TODAY'S SCHEDULE" : `DAY ${selectedDayIdx + 1} OF 7`}
              </span>
            </div>
          </div>

          {/* AM & PM Dual Session Cards */}
          <div className="grid-2col">
            {/* AM Primary Session Card */}
            <div className="glass-panel" style={{ border: '1px solid var(--accent-cyan)' }}>
              <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0, 240, 255, 0.08)' }}>
                <h4 className="panel-title" style={{ color: 'var(--accent-cyan)', fontSize: '0.95rem' }}>
                  🌅 {currentDay.amSession.name}
                </h4>
                <button 
                  onClick={() => handleLogSession(selectedDayIdx, 'am')}
                  className="btn-primary" 
                  style={{ background: 'var(--accent-cyan)', color: '#000', padding: '0.25rem 0.6rem', fontSize: '0.75rem', fontWeight: 'bold' }}
                >
                  LOG AM WORKOUT
                </button>
              </div>
              <div className="panel-content" style={{ padding: '1rem' }}>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: '1rem', borderBottom: '1px solid var(--border-glass)', paddingBottom: '0.5rem' }}>
                  <strong>Goal:</strong> {currentDay.amSession.goal}
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {currentDay.amSession.sections.map((sec, sIdx) => (
                    <div key={sIdx}>
                      <h5 style={{ fontSize: '0.8rem', color: 'var(--accent-yellow)', marginBottom: '0.4rem', fontFamily: 'monospace' }}>{sec.name}</h5>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                        {sec.exercises.map((ex, eIdx) => {
                          const exKey = `${sIdx}-${eIdx}`;
                          const isChecked = !!checkedExercises[`${selectedDayIdx}-am-${exKey}`];
                          return (
                            <label key={eIdx} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.8rem', cursor: 'pointer' }}>
                              <input 
                                type="checkbox" 
                                checked={isChecked} 
                                onChange={e => handleExerciseCheck(selectedDayIdx, 'am', exKey, e.target.checked)}
                                style={{ marginTop: '0.2rem', accentColor: 'var(--accent-cyan)' }}
                              />
                              <span style={{ color: isChecked ? 'var(--text-muted)' : 'var(--text-primary)', textDecoration: isChecked ? 'line-through' : 'none' }}>
                                {ex}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* PM Secondary Session Card */}
            <div className="glass-panel" style={{ border: '1px solid var(--accent-purple)' }}>
              <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(188, 19, 254, 0.08)' }}>
                <h4 className="panel-title" style={{ color: 'var(--accent-purple)', fontSize: '0.95rem' }}>
                  🌙 {currentDay.pmSession.name}
                </h4>
                {currentDay.pmSession.duration > 0 && (
                  <button 
                    onClick={() => handleLogSession(selectedDayIdx, 'pm')}
                    className="btn-primary" 
                    style={{ background: 'var(--accent-purple)', color: '#fff', padding: '0.25rem 0.6rem', fontSize: '0.75rem', fontWeight: 'bold' }}
                  >
                    LOG PM WORKOUT
                  </button>
                )}
              </div>
              <div className="panel-content" style={{ padding: '1rem' }}>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: '1rem', borderBottom: '1px solid var(--border-glass)', paddingBottom: '0.5rem' }}>
                  <strong>Goal:</strong> {currentDay.pmSession.goal}
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {currentDay.pmSession.sections.map((sec, sIdx) => (
                    <div key={sIdx}>
                      <h5 style={{ fontSize: '0.8rem', color: 'var(--accent-pink)', marginBottom: '0.4rem', fontFamily: 'monospace' }}>{sec.name}</h5>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                        {sec.exercises.map((ex, eIdx) => {
                          const exKey = `${sIdx}-${eIdx}`;
                          const isChecked = !!checkedExercises[`${selectedDayIdx}-pm-${exKey}`];
                          return (
                            <label key={eIdx} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.8rem', cursor: 'pointer' }}>
                              <input 
                                type="checkbox" 
                                checked={isChecked} 
                                onChange={e => handleExerciseCheck(selectedDayIdx, 'pm', exKey, e.target.checked)}
                                style={{ marginTop: '0.2rem', accentColor: 'var(--accent-purple)' }}
                              />
                              <span style={{ color: isChecked ? 'var(--text-muted)' : 'var(--text-primary)', textDecoration: isChecked ? 'line-through' : 'none' }}>
                                {ex}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUBTAB 2: PROGRESSIVE OVERLOAD & DOUBLE PROGRESSION */}
      {healthSubTab === 'overload' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="glass-panel" style={{ padding: '1.25rem', borderLeft: '4px solid var(--accent-cyan)' }}>
            <h3 className="panel-title" style={{ color: 'var(--accent-cyan)', marginBottom: '0.5rem' }}>
              The Double Progression System & Auto-Regulation Strategy
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
              Designed for experienced lifters returning after a break. Instead of trying to add weight every week (which leads to plateaus and joint fatigue), follow this two-phase cycle.
            </p>
          </div>

          <div className="grid-2col">
            {/* Overload Rules Matrix */}
            <div className="glass-panel">
              <div className="panel-header">
                <h4 className="panel-title" style={{ fontSize: '0.9rem' }}>Progressive Overload Variable by Exercise Type</h4>
              </div>
              <div className="panel-content" style={{ padding: '1rem' }}>
                <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)', textAlign: 'left', color: 'var(--accent-cyan)' }}>
                      <th style={{ padding: '0.5rem' }}>Movement Type</th>
                      <th style={{ padding: '0.5rem' }}>Overload Variable</th>
                      <th style={{ padding: '0.5rem' }}>Increment Size</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)' }}>
                      <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Heavy Barbell Compounds<br/><span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Squats, Bench, OHP, RDLs</span></td>
                      <td style={{ padding: '0.5rem' }}>Weight First (Double Progression)</td>
                      <td style={{ padding: '0.5rem', color: 'var(--accent-green)' }}>+5–10 lbs once top reps are hit</td>
                    </tr>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)' }}>
                      <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Dumbbell & Cable Accessories<br/><span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Incline DB, Rows, Pulldowns</span></td>
                      <td style={{ padding: '0.5rem' }}>Reps & Form First</td>
                      <td style={{ padding: '0.5rem', color: 'var(--accent-yellow)' }}>+2.5–5 lbs per side / plate notch</td>
                    </tr>
                    <tr>
                      <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>Isolation & Machines<br/><span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Lateral Raises, Leg Curls, Arms</span></td>
                      <td style={{ padding: '0.5rem' }}>Time Under Tension & Volume</td>
                      <td style={{ padding: '0.5rem', color: 'var(--accent-purple)' }}>+1–2 reps or 2s slow eccentric</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* RIR Auto-Regulation & 3 Lock-In Rules */}
            <div className="glass-panel">
              <div className="panel-header">
                <h4 className="panel-title" style={{ fontSize: '0.9rem' }}>RIR & Fatigue Management Timeline</h4>
              </div>
              <div className="panel-content" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.75rem', borderRadius: '4px', border: '1px solid var(--border-glass)' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--accent-green)' }}>WEEKS 1–3 (RIR 2–3)</span>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0.2rem 0 0 0' }}>
                    Leave 2–3 clean reps in the tank on every set. Rebuilds tendon capacity and prevents debilitating soreness.
                  </p>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.75rem', borderRadius: '4px', border: '1px solid var(--border-glass)' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--accent-yellow)' }}>WEEKS 4–5 (RIR 1–2)</span>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0.2rem 0 0 0' }}>
                    Push closer to technical failure on your final work set of each movement.
                  </p>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.75rem', borderRadius: '4px', border: '1px solid var(--border-glass)' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--accent-purple)' }}>WEEK 6 (DELOAD WEEK)</span>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0.2rem 0 0 0' }}>
                    Cut total weight by 20% and set volume by half to allow joints and nervous system to supercompensate.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUBTAB 3: DUAL-SESSION NUTRITION & TIMELINE */}
      {healthSubTab === 'nutrition' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Daily Macronutrient & Hydration Targets Banner */}
          <div className="grid-4col">
            <div className="glass-panel" style={{ padding: '0.75rem', borderLeft: '3px solid var(--accent-green)' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>DAILY PROTEIN</span>
              <h3 style={{ margin: '0.2rem 0 0 0', color: 'var(--accent-green)', fontSize: '1.3rem' }}>180–200g</h3>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>1.0g per lb (Muscle repair & striking)</span>
            </div>
            <div className="glass-panel" style={{ padding: '0.75rem', borderLeft: '3px solid var(--accent-yellow)' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>DAILY CARBS</span>
              <h3 style={{ margin: '0.2rem 0 0 0', color: 'var(--accent-yellow)', fontSize: '1.3rem' }}>270–360g</h3>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>1.5-2.0g per lb (Heavy glycogen fuel)</span>
            </div>
            <div className="glass-panel" style={{ padding: '0.75rem', borderLeft: '3px solid var(--accent-pink)' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>HEALTHY FATS</span>
              <h3 style={{ margin: '0.2rem 0 0 0', color: 'var(--accent-pink)', fontSize: '1.3rem' }}>60–80g</h3>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>0.35-0.4g per lb (Joints & hormones)</span>
            </div>
            <div className="glass-panel" style={{ padding: '0.75rem', borderLeft: '3px solid var(--accent-cyan)' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>HYDRATION RULE</span>
              <h3 style={{ margin: '0.2rem 0 0 0', color: 'var(--accent-cyan)', fontSize: '1.3rem' }}>128 oz (1 Gal)</h3>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>+1-2 Electrolyte packets Tue/Sat</span>
            </div>
          </div>

          <div className="grid-2col">
            {/* Meal Timeline */}
            <div className="glass-panel">
              <div className="panel-header">
                <h4 className="panel-title" style={{ fontSize: '0.9rem' }}>Dual-Session Daily Fueling Timeline</h4>
              </div>
              <div className="panel-content" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.8rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-glass)' }}>
                  <span style={{ color: 'var(--accent-yellow)', fontWeight: 'bold' }}>5:30 AM — Pre-AM Fast Fuel</span>
                  <span>1 Banana or Sourdough + Honey + 16 oz Electrolyte Water</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-glass)' }}>
                  <span style={{ color: 'var(--accent-green)', fontWeight: 'bold' }}>7:30 AM — Post-AM Breakfast</span>
                  <span>3-4 Egg scramble + Spinach + Oatmeal + Berries + Whey</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-glass)' }}>
                  <span style={{ color: 'var(--accent-cyan)', fontWeight: 'bold' }}>12:30 PM — Balanced Lunch</span>
                  <span>6-8 oz Chicken/Turkey + 1.5c Jasmine Rice/Sweet Potato + Broccoli</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-glass)' }}>
                  <span style={{ color: 'var(--accent-purple)', fontWeight: 'bold' }}>4:30 PM — Pre-PM Snack</span>
                  <span>Rice cakes + Peanut Butter + Banana OR Greek Yogurt + Granola</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border-glass)' }}>
                  <span style={{ color: 'var(--accent-pink)', fontWeight: 'bold' }}>7:00 PM — Post-PM Dinner</span>
                  <span>6-8 oz Salmon or Steak + Sweet Potato + Green Salad w/ Avocado Oil</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 'bold' }}>9:30 PM — Pre-Bed Recovery</span>
                  <span>1 cup Cottage Cheese OR Casein Shake + Almond Butter</span>
                </div>
              </div>
            </div>

            {/* Meal Logger Form */}
            <div className="glass-panel">
              <div className="panel-header">
                <h4 className="panel-title" style={{ fontSize: '0.9rem' }}>Log Fuel / Meal Entry</h4>
              </div>
              <div className="panel-content" style={{ padding: '1rem' }}>
                <form onSubmit={(e) => {
                  e.preventDefault();
                  handleFormSubmit(
                    'meals',
                    {
                      ...mealForm,
                      calories: mealForm.calories === '' ? null : parseInt(mealForm.calories),
                      protein_g: mealForm.protein_g === '' ? null : parseFloat(mealForm.protein_g),
                      carbs_g: mealForm.carbs_g === '' ? null : parseFloat(mealForm.carbs_g),
                      fat_g: mealForm.fat_g === '' ? null : parseFloat(mealForm.fat_g)
                    },
                    setMealForm,
                    { date: new Date().toISOString().split('T')[0], meal_type: 'breakfast', description: '', calories: '', protein_g: '', carbs_g: '', fat_g: '' }
                  );
                }} style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  <div className="form-grid" style={{ marginBottom: 0 }}>
                    <div className="form-group">
                      <label className="form-label">Date</label>
                      <input type="date" className="form-input" value={mealForm.date} onChange={e => setMealForm({...mealForm, date: e.target.value})} required />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Meal Type</label>
                      <select className="form-select" value={mealForm.meal_type} onChange={e => setMealForm({...mealForm, meal_type: e.target.value})}>
                        <option value="breakfast">Breakfast</option>
                        <option value="lunch">Lunch</option>
                        <option value="dinner">Dinner</option>
                        <option value="snack">Snack</option>
                      </select>
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Description</label>
                    <input type="text" placeholder="e.g. Scrambled eggs, oatmeal, whey shake" className="form-input" value={mealForm.description} onChange={e => setMealForm({...mealForm, description: e.target.value})} required />
                  </div>
                  <div className="form-grid" style={{ marginBottom: 0 }}>
                    <div className="form-group">
                      <label className="form-label">Calories (kcal)</label>
                      <input type="number" placeholder="450" className="form-input" value={mealForm.calories} onChange={e => setMealForm({...mealForm, calories: e.target.value})} required />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Protein (g)</label>
                      <input type="number" step="0.1" placeholder="40.0" className="form-input" value={mealForm.protein_g} onChange={e => setMealForm({...mealForm, protein_g: e.target.value})} />
                    </div>
                  </div>
                  <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '0.4rem' }}>Log Meal to Athena</button>
                </form>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUBTAB 4: SUNDAY YOGA, RECOVERY & BIOMETRICS */}
      {healthSubTab === 'biometrics' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Sunday Recovery Guide */}
          <div className="glass-panel" style={{ padding: '1.25rem', borderLeft: '4px solid var(--accent-purple)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <h3 className="panel-title" style={{ color: 'var(--accent-purple)' }}>
                🧘 Sunday Athlete Recovery Flow (60 Mins)
              </h3>
              <button 
                onClick={() => {
                  handleFormSubmit(
                    'mindfulness',
                    { date: new Date().toISOString().split('T')[0], activity_type: 'yoga', duration_minutes: 60, notes: '60-Minute Sunday Athlete Recovery Flow (Spinal Decompression, Yin Holds & Breathwork)' },
                    setMindForm,
                    { date: new Date().toISOString().split('T')[0], activity_type: 'yoga', duration_minutes: '60', notes: '' }
                  );
                }}
                className="btn-primary"
                style={{ background: 'var(--accent-purple)', color: '#fff', fontSize: '0.75rem' }}
              >
                LOG SUNDAY YOGA FLOW
              </button>
            </div>
            <div className="grid-4col" style={{ gap: '0.5rem', fontSize: '0.75rem' }}>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '4px' }}>
                <strong style={{ color: 'var(--accent-cyan)' }}>Phase 1 (10m): Spinal Decompression</strong>
                <p style={{ margin: '0.2rem 0 0 0', color: 'var(--text-muted)' }}>Child's pose lat reach (3m), Cat-Cow to thread needle (4m), Down Dog pedals (3m)</p>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '4px' }}>
                <strong style={{ color: 'var(--accent-green)' }}>Phase 2 (15m): Dynamic Hip/Ankle</strong>
                <p style={{ margin: '0.2rem 0 0 0', color: 'var(--text-muted)' }}>World's Greatest Stretch, Low Lunge to Half Splits flow, Garland Pose squat hold (5m)</p>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '4px' }}>
                <strong style={{ color: 'var(--accent-yellow)' }}>Phase 3 (25m): Deep Yin Holds</strong>
                <p style={{ margin: '0.2rem 0 0 0', color: 'var(--text-muted)' }}>Pigeon Pose (3m/side), Frog Pose (4m), Lying Hero (4m), Puppy Pose (3m), Reclined Twist (4m)</p>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '4px' }}>
                <strong style={{ color: 'var(--accent-purple)' }}>Phase 4 (10m): Parasympathetic</strong>
                <p style={{ margin: '0.2rem 0 0 0', color: 'var(--text-muted)' }}>Legs-Up-The-Wall Savasana (10m) with 4s inhale / 6s exhale tempo</p>
              </div>
            </div>
          </div>

          <div className="grid-2col">
            {/* Biometrics Form */}
            <div className="glass-panel">
              <div className="panel-header">
                <h4 className="panel-title" style={{ fontSize: '0.9rem' }}>Log Daily Biometrics & Sleep</h4>
              </div>
              <div className="panel-content" style={{ padding: '1rem' }}>
                <form onSubmit={(e) => {
                  e.preventDefault();
                  handleFormSubmit(
                    'health', 
                    {
                      ...healthForm,
                      weight_lbs: healthForm.weight_lbs === '' ? null : parseFloat(healthForm.weight_lbs),
                      sleep_hours: healthForm.sleep_hours === '' ? null : parseFloat(healthForm.sleep_hours),
                      mood: healthForm.mood === '' ? null : parseInt(healthForm.mood),
                      systolic: healthForm.systolic === '' ? null : parseInt(healthForm.systolic),
                      diastolic: healthForm.diastolic === '' ? null : parseInt(healthForm.diastolic),
                      water_ml: healthForm.water_ml === '' ? 0 : parseInt(healthForm.water_ml),
                      energy_level: healthForm.energy_level === '' ? null : parseInt(healthForm.energy_level),
                      stress_level: healthForm.stress_level === '' ? null : parseInt(healthForm.stress_level)
                    }, 
                    setHealthForm, 
                    { date: new Date().toISOString().split('T')[0], weight_lbs: '', sleep_hours: '', mood: '8', systolic: '', diastolic: '', notes: '', water_ml: '3785', energy_level: '8', stress_level: '3' }
                  );
                }} style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  <div className="form-grid" style={{ marginBottom: 0 }}>
                    <div className="form-group">
                      <label className="form-label">Date</label>
                      <input type="date" className="form-input" value={healthForm.date} onChange={e => setHealthForm({...healthForm, date: e.target.value})} required />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Weight (lbs)</label>
                      <input type="number" step="0.1" placeholder="e.g. 185.0" className="form-input" value={healthForm.weight_lbs} onChange={e => setHealthForm({...healthForm, weight_lbs: e.target.value})} />
                    </div>
                  </div>
                  <div className="form-grid" style={{ marginBottom: 0 }}>
                    <div className="form-group">
                      <label className="form-label">Sleep Hours</label>
                      <input type="number" step="0.5" placeholder="e.g. 7.5" className="form-input" value={healthForm.sleep_hours} onChange={e => setHealthForm({...healthForm, sleep_hours: e.target.value})} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Water Intake (ml)</label>
                      <input type="number" placeholder="3785" className="form-input" value={healthForm.water_ml} onChange={e => setHealthForm({...healthForm, water_ml: e.target.value})} />
                    </div>
                  </div>
                  <div className="form-grid" style={{ marginBottom: 0 }}>
                    <div className="form-group">
                      <label className="form-label">Energy Level (1-10)</label>
                      <select className="form-select" value={healthForm.energy_level} onChange={e => setHealthForm({...healthForm, energy_level: e.target.value})}>
                        {[1,2,3,4,5,6,7,8,9,10].map(n => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Stress Level (1-10)</label>
                      <select className="form-select" value={healthForm.stress_level} onChange={e => setHealthForm({...healthForm, stress_level: e.target.value})}>
                        {[1,2,3,4,5,6,7,8,9,10].map(n => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </div>
                  </div>
                  <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '0.4rem' }}>Save Biometrics</button>
                </form>
              </div>
            </div>

            {/* Workout History */}
            <div className="glass-panel">
              <div className="panel-header">
                <h4 className="panel-title" style={{ fontSize: '0.9rem' }}>Recent Workout Logs</h4>
              </div>
              <div className="panel-content" style={{ padding: '1rem', maxHeight: '350px', overflowY: 'auto' }}>
                {fitnessData.logs.length === 0 ? (
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>No workouts logged yet.</p>
                ) : (
                  <div className="item-list">
                    {fitnessData.logs.map((wk) => (
                      <div key={wk.id} className="list-item" style={{ padding: '0.5rem', marginBottom: '0.35rem' }}>
                        <div className="item-meta">
                          <span className="item-title" style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>{wk.activity_type.toUpperCase()}</span>
                          <span className="item-subtitle" style={{ fontSize: '0.7rem' }}>
                            {wk.date} • {wk.duration_minutes} mins • {wk.calories_burned} kcal
                          </span>
                          {wk.notes && <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginTop: '0.1rem' }}>{wk.notes}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default FitnessTab;
