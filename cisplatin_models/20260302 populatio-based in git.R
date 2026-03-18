#population-based kinetic model for cisplatin in human
#species: human
#compound: cisplatin
#author: Kiri Romano Olmedo

#PBK model for cisplatin with detailed kidney compartment and active renal transport

#_____________________________________________________

#packages
#C:/Program Files/R
#-------------------------------------------------------------------------------------------------------------------------------------------
install.packages("patchwork")
install.packages("rxode2")
install.packages("tidyverse")
install.packages("ggplot2")
install.packages("dplyr")
install.packages("mrgsolve")
library(patchwork)
library(rxode2)
library(tidyverse)
library(ggplot2)
library(dplyr)
library(mrgsolve)
#_____________________________________________________

# Time parameter for simulations
amount.units = "umol"
time.units = "h"
nbr.doses = 1             	# Number of doses
time.0 = 0                	# Time start dosing
time.end = 48           	# Time end of simulation
time.frame = 0.01     	# Time steps of simulation

#initialize model

initmodel <- function(){
  inits <<- c(
    AB=0,
    AF=0,
    AS=0,
    AR=0,
    AKB=0,
    AFIL=0,
    ARK=0,
    APT=0,
    AUR=0,
    AOCT=0,
    AMATE=0,
    GF=0)
}
#__model______________________________________________


##physiological parameters##
#from Brown 1997, Maass 2019, Valetin 2022
Model <<- rxode2({
  BW = 70		  	#body weight in kg
  QFC = 0.05		#fractional blood flow to fat tissue, unitless (/kg BW)
  QSC = 0.27		#fractional blood flow to slowly perfused tissue, unitless (/kg BW)
  QRC = 0.49		#fractional blood flow to richly perfused tissue, unitless (/kg BW)
  QKBC = 0.19		#fractional blood flow to arterial kidney blood, unitless (/kg BW)
  
  VBC = 0.0771	#fractional volume of arterial blood in L/kg BW
  VFC = 0.2142	#fractional volume of fat in L/kg BW
  VSC = 0.58		#fractional volume of slowly perfused tissue in L/kg BW
  VRC = 0.1243	#fractional volume of richly perfused tissue in L/kg BW
  VKBC = 0.18*0.0044		#fractional volume of arterial kidney blood in L/kg BW
  VRKC = 0.21*0.0044		#fractional volume of rest of kidney in L/kg BW
  VPTC = 0.28*0.0044		#fractional volume of proximal tubule in L/kg BW
  VFILC = 0.33*0.0044		#fractional volume of filtrate in L/kg BW
  VTKC = 0.0044		      #fractional volume of total kidney in L/kg BW
  
  ##calculated physiological parameters##
  QC = 15*(BW^0.74)	#cardiac output in L/h (Brown 1997)
  QF = QFC*QC		    #blood flow to fat tissue in L/h
  QS = QSC*QC		    #blood flow to slowly perfused tissue in L/h
  QR = QRC*QC		    #blood flow to richly perfused tissue in L/h
  QKB = QKBC*QC	  	#blood flow to kidney blood in L/h
  
  VB = VBC*BW	    	#volume arterial blood in L
  VF = VFC*BW		    #volume fat tissue in L
  VS = VSC*BW		    #volume slowly perfused tissue in L
  VR = VRC*BW		    #volume richly perfused tissue in L
  VKB = VKBC*BW		  #volume arterial kidney blood in L
  VRK = VRKC*BW	  	#volume rest of kidney in L
  VPT = VPTC*BW	  	#volume of proximal tubule in L
  VFIL = VFILC*BW		#volume of filtrate in L
  VTK = VTKC*BW     #volume of total kidney in L
  
  
  ##physicochemical parameters##
  #obtained with qivivetools.wur.nl
  PF =  0.0605 	#blood to fat partition coefficient, unitless
  PS = 0.2512 	#blood to slowly perfused tissue partition coefficient, unitless
  PR = 0.2678 	#blood to richtly perfused tissue  partition coefficient, unitless
  PRK = 0.2698 	#blood to rest of kidney partition coefficient, unitless
  
  
  ##calculations##
  #concentrations in tissue
  CB=AB/VB          #blood in umol
  CP=(CB/BPR)*Fup	  #plasma in umol
  CF=AF/VF          #fat in umol
  CS=AS/VS          #slowly perfused tissue in umol
  CR=AR/VR          #rapidly perfused tissue in umol
  CKB=AKB/VKB       #kidney blood in umol
  CRK=ARK/VRK       #rest of kidney tissue in umol
  CPT=APT/VPT       #proximal tubule in umol
  CFIL=AFIL/VFIL    #filtrate in umol
  CUR=AUR/VUR       #urine in umol
  
  #concentrations in venous blood per tissue
  CVF = CF / PF     #Venous blood from fat 
  CVS = CS / PS     #Venous blood from slowly perfused tissue
  CVR = CR / PR     #Venous blood from rapidly perfused tissue
  CVRK = CRK / PRK  #Venous blood from rest kidney
  
  
  #kinetic parameters
  Fup = 0.8         #fraction unbound cisplatin in plasma
  BPR = 2.15	    	#blood plasma ratio
  Fub = 1/(0.55*((1/Fup)-1)+1)	#fraction unbound cisplatin in blood
  GFR = 0.1071 * BW             #glomerular filtration rate human in L/h
  kURINE = 0.083    #urine production in L/h, based on 83 ml/h
  #VUR = kURINE*time
  
  
  #OCT2-mediated transport
  MK = VTKC*BW*1000		    #mass total kidney in gram
  PTC = 6E7			          #number of pt cells per gram kidney
  PTPROTEIN = 2.0e-9		  #gram protein/proximal tubule cell
  MPT = MK*PTC*PTPROTEIN	#mass proximal tubule in gram based on BW
  
  
  SFOCT = 35      #scaling factor OCT2
  PEROCT = 1      #percentage OCT2 activity
  VmaxOCTc = 13.7 #Vmax in pmol/mg/min (from Sprowl 2013)
  VmaxOCT = (VmaxOCTc/1000000)*60*MPT*1000*SFOCT*PEROCT #Vmax in umol/h, maximum rate of uptake cisplatin by OCT2
  KmOCT = 11.4 		#Km in umol/L, transport constant of cisplatin by OCT2 (from Sprowl 2013)
  
  SFMATE = 0.06		#scaling factor MATE
  CLMATE = (VmaxOCTc/KmOCT)*60*MPT*5*SFMATE/1000 #clearance mediated by MATE
  
  
  ##differential equations##
  
  #glomerular filtration
  rate_GF = (CKB*GFR*(Fup/BPR))
  d/dt(GF) = 	rate_GF
  
  #fat
  d/dt(AF) = QF*(CB-CVF)
  
  #slowly perfused tissue
  d/dt(AS) = QS*(CB-CVS)
  
  #richly perfused tissue
  d/dt(AR) = QR*(CB-CVR)
  
  #blood
  d/dt(AB) = (QF*CVF + QS*CVS + QR*CVR + QKB*CVRK) - CB*(QF + QS + QR + QKB)
  
  
  ####kidney####
  #OCT2
  rate_OCT = (VmaxOCT*(CKB*(Fup/BPR)))/(KmOCT+(CKB*(Fup/BPR))) #rate of active transport from kidney blood into proximal tubule in umol/h
  d/dt(AOCT) = rate_OCT
  
  #MATEs
  rate_MATE = CLMATE*CPT
  d/dt(AMATE) = rate_MATE
  
  #kidney blood
  d/dt(AKB) = QKB*(CB) - (QKB*CKB) - rate_GF - rate_OCT
  
  #rest of kidney tissue
  d/dt(ARK) = QKB*(CKB-CVRK)
  
  #proximal tubule
  d/dt(APT) = rate_OCT - rate_MATE
  
  #urine
  d/dt(AUR) = CFIL*kURINE
  d/dt(VUR) = kURINE
  
  #filtrate
  d/dt(AFIL) = rate_GF + rate_MATE - d/dt(AUR)
  
  
  
})


###__dosing___________________________________

BW = 70                             #in kg
MW = 300.5                          #molecular weight in g/mol
IVDOSEm2 = 80
IVDOSEmg = (IVDOSEm2*1.78)/BW          #IV dose in mg/kg
IVDOSEUMOL = (IVDOSEmg*1E-3/MW)*1E+6   #IV dose as umol/kg
IVDOSE = IVDOSEUMOL*BW			           #given IV dose in umol for 70kg BW

#IVDOSEUG = IVDOSEmg*1000 #IV dose in µg/kg
#IVDOSE = IVDOSEUG*BW	

# Define the event table
ev <- eventTable(amount.units = "umol", time.units = "h") #%>% 
ev$add.sampling(seq(0, 50, by = 0.1)) #%>% 

INFUSION_DURATION <- 1  # infusion duration in hours

# Add the dosing event with an infusion over 1 hour
ev$add.dosing(
  dose = IVDOSE ,
  dosing.to = "AB" ,
  dur = INFUSION_DURATION)

ModelOutput <<- solve(Model, NULL, events = ev, inits = inits, cores = 4)

results <- data.frame(
  IVDOSE = IVDOSE,
  Tmax = ModelOutput[which.max(ModelOutput$CP), "time"],
  Cmax = max(ModelOutput$CP)
)
new_row <- data.frame(
  IVDOSE = IVDOSE,
  Tmax = ModelOutput[which.max(ModelOutput$CP), "time"],
  Cmax = max(ModelOutput$CP)
)

results <- rbind(results, new_row)


##__MassBalance___
colsAll <-c("AF","AS","AR","ARK","AB","AKB","AUR","AFIL","APT")

CalcTotBodAll <- function(time_points, IVDOSE, INFUSION_DURATION) {
  TotBodAll <- numeric(length(time_points))
  for (i in 1:length(time_points)) {
    time <- time_points[i]
    if (time <= INFUSION_DURATION) {
      TotBodAll[i] <- IVDOSE * (time / INFUSION_DURATION)
    } else {
      TotBodAll[i] <- IVDOSE
    }
  }
  return(TotBodAll)
}

# Apply the function to get the administered amount at each time point
TotBodAll <- CalcTotBodAll(ModelOutput[,"time"], IVDOSE, INFUSION_DURATION)

# Calculate what goes in (amount in the model)
CalcBodAll <- rowSums(ModelOutput[, colsAll])

# Calculate mass balance
MassBall <- TotBodAll - CalcBodAll + 1

# Calculate mass error (% of mass lost)
ErrorAll <- (TotBodAll - CalcBodAll) / (TotBodAll + 10^(-30)) * 100

# Compile Mass Balance data into a dataframe
MassBal <- cbind("time" = ModelOutput[,"time"], MassBall, ErrorAll)
df_MassBal <- as.data.frame(MassBal)

#Plot the massbalance
print(
  ggplot(data = df_MassBal) +
    geom_line(aes(x = time,
                  y = MassBall)) +
    geom_line(aes(x = time,
                  y = ErrorAll)) +
    labs(title = "MB All",
         x = "Time (h)",
         y = "Concentration (umol/L)") 
)

#Plot blood concentration 
print(
  
  IVCisplatin <- ggplot(ModelOutput, aes(x=time, y=CP)) + 
    geom_line(linewidth = 1)+
    labs(title = "Plasma",
         x = "Time (h)",
         y = "Concentration (µM)",
         shape = "In vivo",
         linetype = "In silico") +
    theme_bw() +
    theme(
      plot.title = element_text(hjust = 0.5, size = 16, face = "bold"),
      axis.title = element_text(size = 14),
      legend.title = element_text(size = 12)
    ) +
    xlim(0,50)+ 
    scale_y_continuous(limits = c(0,50))  
)

###checks for running the model###
.libPaths()
Sys.getenv("R_USER")
Sys.getenv("HOME")
getwd()
normalizePath("~")
install.packages("usethis")

