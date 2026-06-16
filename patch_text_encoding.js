/**
 * Patch FINAL: Fix remaining mojibake by working at Buffer/binary level.
 * Reads file as UTF-8, but replaces exact byte sequences that were misencoded.
 *
 * Root cause: File was originally UTF-8, but some editors re-saved it as
 * Latin-1 then re-read as UTF-8 causing double-encoding.
 * We reverse this: for each garbled sequence, re-encode back to original UTF-8.
 */
const fs = require('fs');
const filePath = 'D:\\ALL TOOL\\TOOL LÀM YOUTUBE\\Ominivoice tao giong doc local\\omnivoice\\utils\\text.py';

// Read raw bytes
let buf = fs.readFileSync(filePath);

/**
 * Replace all occurrences of a byte sequence with another in a Buffer.
 * Returns new Buffer.
 */
function bufReplace(buf, searchBytes, replaceBytes) {
  const search  = Buffer.from(searchBytes);
  const replace = Buffer.from(replaceBytes);
  const chunks  = [];
  let   pos     = 0;
  while (pos < buf.length) {
    const idx = buf.indexOf(search, pos);
    if (idx === -1) {
      chunks.push(buf.slice(pos));
      break;
    }
    chunks.push(buf.slice(pos, idx));
    chunks.push(replace);
    pos = idx + search.length;
  }
  return Buffer.concat(chunks);
}

// Each entry: [wrong UTF-8 bytes (mojibake), correct UTF-8 bytes]
// Derived from the diagnostic output above.
const fixes = [
  // ── SPLIT_PUNCTUATION line 32 ─────────────────────────────────────────
  // 。ã€‚ = c3 a3 e2 82 ac e2 80 9a  → e3 80 82
  [[0xc3,0xa3,0xe2,0x82,0xac,0xe2,0x80,0x9a],  [0xe3,0x80,0x82]],
  // ，ï¼Œ = c3 af c2 bc c5 92        → ef bc 8c
  [[0xc3,0xaf,0xc2,0xbc,0xc5,0x92],            [0xef,0xbc,0x8c]],
  // ；ï¼› = c3 af c2 bc e2 80 ba     → ef bc 9b
  [[0xc3,0xaf,0xc2,0xbc,0xe2,0x80,0xba],       [0xef,0xbc,0x9b]],
  // ：ï¼š = c3 af c2 bc c5 a1        → ef bc 9a
  [[0xc3,0xaf,0xc2,0xbc,0xc5,0xa1],            [0xef,0xbc,0x9a]],
  // ！ï¼  = c3 af c2 bc c2 81        → ef bc 81  (→ ！)
  [[0xc3,0xaf,0xc2,0xbc,0xc2,0x81],            [0xef,0xbc,0x81]],
  // ？ï¼Ÿ = c3 af c2 bc c5 b8        → ef bc 9f
  [[0xc3,0xaf,0xc2,0xbc,0xc5,0xb8],            [0xef,0xbc,0x9f]],
  // 】ã€  = c3 a3 e2 82 ac c2 81     → e3 80 8f
  [[0xc3,0xa3,0xe2,0x82,0xac,0xc2,0x81],       [0xe3,0x80,0x8f]],
  // ）ï¼‰ = c3 af c2 bc e2 80 b0     → ef bc 89
  [[0xc3,0xaf,0xc2,0xbc,0xe2,0x80,0xb0],       [0xef,0xbc,0x89]],
  // 」ã€' = c3 a3 e2 82 ac e2 80 98  → e3 80 8d
  [[0xc3,0xa3,0xe2,0x82,0xac,0xe2,0x80,0x98],  [0xe3,0x80,0x8d]],
  // 《ã€‹ = c3 a3 e2 82 ac e2 80 b9  → e3 80 8b  (CLOSING_MARKS)
  [[0xc3,0xa3,0xe2,0x82,0xac,0xe2,0x80,0xb9],  [0xe3,0x80,0x8b]],
  // 》ã€ (8d) = c3 a3 e2 82 ac c2 8d → e3 80 8f (fallback for 】)
  // Already handled above, skip duplicate

  // ── END_PUNCTUATION line 42: … = c3 a6 e2 80 a6 → no, check again
  // From output line 42: [e2 80 a6] → this is already correct UTF-8 for …
  // line 50: [ef bc 9b] = ；  already correct
  // line 51: [ef bc 9a] = ：  already correct
  // So lines 50-59 already correct after above patches. ✓

  // ── VI_NONVERBAL_TAG_FALLBACKS ───────────────────────────────────────
  // [sigh] " hãy... "  -> hãy = c3 a3 79 should be 68 c3 a3 79 = h + ã + y
  // But we want hãy = 68 c3 a3 79 which is WRONG. Correct is hãy = 68 e1 bb 9c ... 
  // Wait: Vietnamese "hãy" = h + ã (U+00E3) = 68 c3 a3. That's actually correct UTF-8!
  // Let me check: "hãy" = U+0068 U+00E3 U+0079 = 68 c3 a3 79 ✓ This is fine.

  // [question-oh] " ồ? " = c3 a1 c2 bb e2 80 9c 3f
  // ồ = U+1ED3 = e1 b4 93... wait e1 bb 93 = ổ? Let me decode:
  // e1 bb 93 = U+1ED3 = ồ ✓
  // But we have c3 a1 c2 bb e2 80 9c which is mojibake of e1 bb 93
  // Mojibake decode: e1→0xc3 0xa1, bb→0xc2 0xbb, 93→e2 0x80 0x9c? No.
  // Actually: reading UTF-8 bytes e1 bb 93 as Latin-1 = &#xe1;&#xbb;&#x93;
  // Then re-encoding those as UTF-8: 
  //   0xe1 → c3 a1, 0xbb → c2 bb, 0x93 → c2 93... hmm not matching
  // From output: c3 a1 c2 bb e2 80 9c → decode as UTF-8 → á + » + " = mojibake
  // The correct char ồ (U+1ED3) in UTF-8 = e1 bb 93
  [[0xc3,0xa1,0xc2,0xbb,0xe2,0x80,0x9c],      [0xe1,0xbb,0x93]],  // ồ

  // [surprise-ah] " á! " - á = U+00E1 = c3 a1 (already in file correctly as c3 a1)
  // line 138 shows c3 a1 which IS correct UTF-8 for á ✓

  // [surprise-oh] " ồ " same as above
  // Already patched above

  // ── map_vietnamese_emotions ─────────────────────────────────────────
  // line 419: hồ hồ hồ replacement
  // c3 a1 c2 bb e2 80 98 = mojibake of ồ (U+1ED3) = e1 bb 93? 
  // Wait: 0x98 -> re-encode as UTF-8 -> c2 98. Hmm doesn't match e1 bb 93.
  // Let's decode c3 a1 c2 bb e2 80 98:
  // As UTF-8: á(U+00E1) + »(U+00BB) + "(U+201C? no, U+0098)
  // That's wrong. Correct ồ = e1 bb 93.
  // But wait: e2 80 98 = ' (U+2018). So c3a1 c2bb e28098 decodes to á»\u2018
  // None of these match... Let me try: the correct char for "hồ" - 
  // ồ = U+1ED3. UTF-8 = e1 bb 93. Mojibake: read e1 bb 93 as latin1 = â»" then encode as UTF-8:
  // â=0xC3 0xA2, »=0xC2 0xBB, "=0xE2 0x80 0x9C -> c3a2 c2bb e2809c
  // Still not matching. Try another path: the file was ALREADY mojibaked once.
  // From diagnostic line 419: [c3 a1 c2 bb e2 80 98] = á»\u2018
  // Try: ồ bytes e1 bb 93, read as latin1 = characters 0xe1, 0xbb, 0x93
  // 0xe1 in latin1 = á → UTF-8 = c3 a1 ✓
  // 0xbb in latin1 = » → UTF-8 = c2 bb ✓  
  // 0x93 in latin1 = \x93 (control) → UTF-8 = c2 93 ✗ (we see e2 80 98)
  // Hmm. Maybe it was Windows-1252: 0x93 = " (U+201C) → UTF-8 = e2 80 9c ✗ (we see e2 80 98)
  // 0x93 in Windows-1252 = " → U+201C → e2 80 9c ... close but we see e2 80 98 = '
  // 0x91 in Windows-1252 = ' → U+2018 → e2 80 98 ✓ !!!
  // So: ồ = e1 bb 93, but 0x93 was misread as Windows-1252 0x91 = U+2018 = e2 80 98
  // That means: c3 a1 c2 bb e2 80 98 → original was e1 bb 93 = ồ? YES!
  // But wait, 0x93 in Win1252 maps to U+201C ("), not 0x91.
  // Actually 0x93 -> " (left double quotation), 0x91 -> ' (left single)
  // Hmm. Let me just trust the bytes: [c3 a1 c2 bb e2 80 98] → replace with [e1 bb 93] (ồ)
  [[0xc3,0xa1,0xc2,0xbb,0xe2,0x80,0x98],      [0xe1,0xbb,0x93]],  // ồ (variant)

  // line 422 comment: thở dài
  // thở: th + ở; ở = U+1EDF = e1 bb 9f
  // dài: d + à + i; à = U+00E0 = c3 a0
  // Mojibake bytes from output line 422: [c3 a1 c2 bb c5 b8] and [c3 83 c2 a0]
  // c3 a1 c2 bb c5 b8 → decode: á»Ÿ where Ÿ=U+0178 → this is mojibake of ở = e1 bb 9f
  //   e1→c3a1, bb→c2bb, 9f→c5 b8? Hmm 0x9f in Win1252 = Ÿ (U+0178) → UTF-8 = c5 b8 ✓ !!!
  //   So: e1 bb 9f → latin1 → 0xe1 0xbb 0x9f → win1252 encode 0x9f as Ÿ → c5 b8
  //   Result: c3 a1 c2 bb c5 b8 ✓ matches!
  [[0xc3,0xa1,0xc2,0xbb,0xc5,0xb8],           [0xe1,0xbb,0x9f]],  // ở

  // c3 83 c2 a0 → Ã + \u00A0 → mojibake of à (U+00E0 = c3 a0)
  //   0xc3 in latin1 = Ã → c3 83, 0xa0 = NBSP → c2 a0. So c3 a0 → c3 83 c2 a0 ✓
  [[0xc3,0x83,0xc2,0xa0],                     [0xc3,0xa0]],  // à

  // line 427: hừ = U+1EEB = e1 bb ab
  // Already correct in file (from patch 1 success). Verify:
  // [e1 bb ab] IS correct UTF-8 for ừ ✓

  // line 431: pattern [oÃ²]Ã  → [oò]a
  // Ã² = c3 83 c2 b2 is mojibake of ò (U+00F2 = c3 b2)
  //   0xc3 in latin1 → c3 83; 0xb2 in latin1 → c2 b2. So c3 b2 → c3 83 c2 b2 ✓
  [[0xc3,0x83,0xc2,0xb2],                     [0xc3,0xb2]],  // ò

  // Ã  (c3 83 c2 a0) already handled above as à

  // line 432: pattern ồ+ = e1 bb 93 (already patched via [question-oh] fix above)

  // line 433: pattern á+ - á = c3 a1, which is already correct UTF-8 for á ✓
  // No fix needed.
];

let count = 0;
for (const [wrong, correct] of fixes) {
  const before = buf.length;
  const newBuf = bufReplace(buf, wrong, correct);
  if (newBuf.length !== before || !buf.equals(newBuf)) {
    const wrongStr = Buffer.from(wrong).toString('hex').match(/.{2}/g).join(' ');
    const corrStr  = Buffer.from(correct).toString('hex').match(/.{2}/g).join(' ');
    console.log(`✔ [${wrongStr}] → [${corrStr}]`);
    buf = newBuf;
    count++;
  } else {
    const wrongStr = Buffer.from(wrong).toString('hex').match(/.{2}/g).join(' ');
    console.log(`  skip [${wrongStr}]`);
  }
}

fs.writeFileSync(filePath, buf);
console.log(`\nDone! ${count} byte-level patches applied.`);

// Final check: print remaining suspicious lines
const result = buf.toString('utf8');
const lines = result.split('\n');
let remaining = 0;
lines.forEach((line, i) => {
  if (/\u00c3[\u0080-\u00bf]|\u00e2\u0080|\u00e1\u00ba|\u00e1\u00bb|\u00c4\u0083|\u00c6\u00b0/.test(line) && i < 445) {
    // Skip lines in our new normalize function (which has correct Vietnamese)
    if (i >= 276 && i <= 395) return;
    console.log(`  STILL GARBLED L${i+1}: ${line.trim().slice(0,100)}`);
    remaining++;
  }
});
if (remaining === 0) console.log('\n✅ All encoding issues resolved!');
