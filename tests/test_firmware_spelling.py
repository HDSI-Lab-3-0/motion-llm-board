"""Compile real sketch spelling functions with a tiny desktop motor substitute.

Requires g++ or clang++ on PATH. No physical motors are used.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    import re
    match = re.search(r'(?:bool|void) ' + name + r'\([^;]*?\)\s*\{', source)
    if not match:
        raise AssertionError(f'Missing firmware function: {name}')
    depth = 1
    end = match.end()
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


class FirmwareSpellingTests(unittest.TestCase):
    def test_real_firmware_motion_sequence(self):
        compiler = shutil.which('g++') or shutil.which('clang++')
        if not compiler:
            self.skipTest('Install g++ or clang++ to run the firmware motion harness')
        source = (ROOT / 'hardware/SPELL_numbers.ino').read_text()
        # Keep the real coordinate maps and repeat tuning from the sketch.
        maps = source[source.index('struct Target {'):source.index('// Special targets')]
        tuning = source[source.index('const unsigned long repeatLetterPauseMs'):source.index('// Homing tuning')]
        import re
        center = '\n'.join(re.findall(r'float [xy]CenterMm = [^;]+;', source))
        names = ['findLetter', 'findNumber', 'numberWordToDigit', 'moveNumberChar',
                 'moveLetterChar', 'goCenter', 'repeatLetterDeparture', 'spellToken', 'spellWord']
        harness = r'''
#include <cassert>
#include <cstring>
#include <cctype>
#include <cmath>
#include <string>
#include <vector>
#define F(s) s
struct SerialStub {
 std::string log;
 template<class T> void print(T) {}
 void print(float, int) {}
 void println(float, int) {}
 void println(const char* s) { log += std::string(s) + "\n"; }
 template<class T> void println(T) {}
} Serial;
struct Point { float x,y; };
std::vector<Point> moves;
bool known = true;
float xMinMm=-8, xMaxMm=8, yMinMm=-30, yMaxMm=40;
bool fullPositionKnown() { return known; }
bool inBounds(float x,float y) {
 return x>=xMinMm && x<=xMaxMm && y>=yMinMm && y<=yMaxMm;
}
void moveBlockingTo(float x,float y) {
 if(!inBounds(x,y)) { Serial.println("ERR out_of_bounds"); return; }
 moves.push_back({x,y});
}
void delay(unsigned long) {}
bool isAlphaNumeric(char c) { return std::isalnum(static_cast<unsigned char>(c)); }
void goYes() { moveBlockingTo(7,33); }
void goNo() { moveBlockingTo(7,-25); }
'''
        harness += maps + tuning + center + '\n'.join(function(source, n) for n in names)
        harness += r'''
void check(const char* word, int repeats) {
 moves.clear(); Serial.log.clear();
 char token[50]; std::strcpy(token,word); spellWord(token);
 assert(moves.size()==std::strlen(word)+repeats);
 unsigned p=0;
 for(unsigned i=0; word[i]; ++i) {
   float x,y; assert(findLetter(word[i],x,y));
   if(i && word[i]==word[i-1]) {
     assert(moves[p].x==xCenterMm && moves[p].y==yCenterMm); ++p;
   }
   assert(moves[p].x==x && moves[p].y==y); ++p;
 }
 assert(Serial.log.find("OK SPELL_DONE")!=std::string::npos);
}
int main() {
 check("GOD",0); check("GOOD",1); check("APPLE",1);
 check("BOOKKEEPER",3); check("AAA",2); check("ABBA",1);
 check("AAAAAAAAAAAAAAAAAAA",18);
 for(char c='A'; c<='Z'; ++c) { char s[]={c,c,0}; check(s,1); }
 check("A",0); check("A",0);
 moves.clear(); char digits[]="11"; spellWord(digits); assert(moves.size()==3);
 assert(moves[1].x==xCenterMm && moves[1].y==yCenterMm);
 moves.clear(); char four[]="FOUR"; spellWord(four); assert(moves.size()==1);
 moves.clear(); char yes[]="YES"; spellWord(yes); assert(moves.size()==1);
 moves.clear(); char no[]="NO"; spellWord(no); assert(moves.size()==1);
 moves.clear(); known=false; assert(!repeatLetterDeparture('O')); assert(moves.empty());
 known=true; xCenterMm=-9;
 moves.clear(); Serial.log.clear(); char bad[]="OO"; spellWord(bad);
 assert(Serial.log.find("ERR repeat_center_invalid")!=std::string::npos);
 assert(Serial.log.find("OK SPELL_DONE")==std::string::npos);
 xCenterMm=-3; yCenterMm=32;
 moves.clear(); assert(!repeatLetterDeparture('O')); assert(moves.empty());
}
'''
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory) / 'spelling.cpp'
            binary = Path(directory) / ('spelling.exe' if os.name == 'nt' else 'spelling')
            cpp.write_text(harness)
            subprocess.run([compiler, '-std=c++11', str(cpp), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
