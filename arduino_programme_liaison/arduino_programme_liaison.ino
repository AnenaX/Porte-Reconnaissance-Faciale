#include "MotorDriver.h"
MotorDriver motor;
long temps = millis();
int position;
int pinInterupteur = 7;
int pinCompteurTour = 2;
long compteur_high;
int valeurCompteur;
bool mode;
long compteur;
int x;

void setup(){
motor.begin();
Serial.begin(115200);
pinMode(pinInterupteur ,INPUT_PULLUP);
pinMode(pinCompteurTour ,INPUT_PULLUP);
attachInterrupt(digitalPinToInterrupt(2), compteur_externe, RISING);
//quand il va y avoir un RISING(changement d'état de 0 --> 1, comme un high) 
//sur la pin 2, on execute le sous programme compteur_externe.
}
void loop()
{
position = digitalRead(7);

if (Serial.available()){
  x = Serial.read();
  if (x == 061) {
    
  if (position == 0){ //si l'interruptreur est pressé
    motor.brake(0);
    delay(500);
    compteur= 0;
    mode = false;//mode fermeture  
 
    } else {
     mode = true;//mode ouverture
     }
    
if (mode == true){
  motor.speed(0, -100); //ouvre la porte
  }
    
if (mode == false){//ferme la porte
  while (compteur < 9100){//compteur de tour
    motor.speed(0, 200);
     }
    }
   }
  }
 }
void compteur_externe(){// ajoute 1 au compteur
compteur++;
} 
      
     
   
 
 
   

   
