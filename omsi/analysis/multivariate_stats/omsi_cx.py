from omsi.analysis.omsi_analysis_base import omsi_analysis_base
from omsi.analysis.omsi_analysis_data import omsi_analysis_data
from omsi.shared.omsi_dependency import *
import numpy as np

###############################################################
#  1) Basic integration of your analysis with omsi (Required) #
###############################################################
class omsi_cx(omsi_analysis_base) :
    """Template intended to help with the development of new analysis classes.
    
       Search for EDIT_ME to find locations that need to be changed.
       
       EDIT_ME: Replace this text with the appropriate documentation for the analysis.
    
    """
    
    #This internal dict is used to avoid errors due to misinterpretation of the usage of dimensions
    dimension_index = {  'imageDim' : 0 , 'pixelDim' : 1}
    

    def __init__(self, nameKey="undefined"):
        """Initalize the basic data members"""
        
        """EDIT_ME Change the class-name to your class to call the init function of omsi_analysis_base"""
        super(omsi_cx,self).__init__()
        """EDIT_ME Add a list of names of input parameters for your analysis"""
        self.parameter_names = ['msidata', 'rank', 'objectiveDim' ]
        """EDIT_ME Add a list of output data generated by your analysis"""
        self.data_names = ['infIndices', 'levScores' ]
        self.analysis_identifier = nameKey
        
    
    def execute_analysis(self) :
        """ EDIT_ME:
        
            Replace this text with the appropriate documentation for the analysis.
            Describe what your analysis does and how a user can use it. Note, a user will
            call the function execute(...) which takes care of storing parameters, collecting
            execution data etc., so that you only need to implement your analysis, the rest
            is taken care of by omsi_analysis_base. omsi uses Sphynx syntax for the 
            documentation.
           
            Keyword Arguments:

            :param mydata: ...
            :type mydata: ...
           
        """
        
        #Setting Default Values
        if not self['rank'] :
            self['rank']=10
        if not self['objectiveDim'] :
            self['objectiveDim']=self.dimension_index['imageDim']
        
        #getting the values into local variables            
        msidata = self['msidata'][:] #Load all MSI data
        originalShape = msidata.shape
        rank = self['rank'][0]
        objectiveDim = self['objectiveDim'][0]
  
        #Convert the input data to a 2D matrix for processing by the leverage score algorithm
        numBins   = msidata.shape[-1]
        numPixels = msidata.size / numBins #The last data dimension is assumed to contain the spectra
        msidata = msidata.reshape(numPixels, numBins).transpose()
        
        #Compute the CX decomposition
        levScores = self.comp_lev_exact(msidata, rank, objectiveDim)
        infIndices = levScores.argsort()[::-1]
        
        #If the leverage scores are computed for pixels, then, convert back to image space
        if self['objectiveDim']==self.dimension_index['pixelDim'] :
            levScores  = levScores.reshape(  originalShape[0:-1] )
            infIndices = infIndices.reshape( originalShape[0:-1] )

        #Safe the output results
        self['levScores'] = levScores
        self['infIndices'] = infIndices
    

    def comp_lev_exact(self, A, k, axis):
        """ This function computes the column or row leverage scores of the input matrix.
        
          
            :param A: n-by-d matrix
            :param k: rank parameter, k <= min(n,d)
            :param axis: 0: compute row leverage scores; 1: compute column leverage scores.
        
            :returns: 1D array of leverage scores. If axis = 0, the length of lev is n.  otherwise, the length of lev is d.
        """
        U, D, V = np.linalg.svd(A, full_matrices=False)

        if axis == 0:
            lev = np.sum(U[:,:k]**2,axis=1)
        else:
            lev = np.sum(V[:k,:]**2,axis=0)
        
        return lev
    
    
    ###############################################################
    #  2) Integrating your analysis with the OpenMSI              #
    #     web-based viewer (Recommended)                          #
    ###############################################################

    @classmethod
    def v_qslice(cls , anaObj , z , viewerOption=0) :
        """Get 3D analysis dataset for which z-slices should be extracted for presentation in the OMSI viewer
        
           :param anaObj: The omsi_file_analysis object for which slicing should be performed 
           :param z: Selection string indicting which z values should be selected.
           :param viewerOption: If multiple default viewer behaviors are available for a given analysis then this option is used to switch between them.
           
           :returns: numpy array with the data to be displayed in the image slice viewer. Slicing will be performed typically like [:,:,zmin:zmax].
           
        """
        #Convert the z selection to a python selection
        from omsi.shared.omsi_data_selection import selection_string_to_object
        zselect = selection_string_to_object(z) #Convert the selection string to a python selection

        """EDIT_ME Specify the number of custom viewerOptions you are going to provide for qslice"""
        currObjectiveDim = anaObj['objectiveDim'][0]
        if currObjectiveDim  == cls.dimension_index['imageDim']:
            numCustomViewerOptions = 1
        else:
            numCustomViewerOptions = 2

        #Expose the qslice viewer functionality of any data dependencies
        if viewerOption >= numCustomViewerOptions :
            print "HERE"
            return super(omsi_cx,cls).v_qslice( anaObj , z, viewerOption=viewerOption-numCustomViewerOptions)
        elif viewerOption == 0 and currObjectiveDim  == cls.dimension_index['imageDim']:
            infIndices = anaObj['infIndices'][zselect]
            myObj = omsi_cx()
            myObj.read_from_omsi_file( analysisObj=anaObj , \
                                       load_data = False, \
                                       load_parameters = False )
            return myObj['msidata'][:,:,infIndices]
        elif viewerOption == 0 and currObjectiveDim  == cls.dimension_index['pixelDim']:
            return anaObj['levScores'][:]
        elif viewerOption == 1 and currObjectiveDim  == cls.dimension_index['pixelDim']:
            return anaObj['infIndices'][:]
        
        """EDIT_ME 
        
           Define your custom qslice viewer options. Here you need to handle all the different
           behaviors that are custom to your analysis. Below a simple example.
                   
           if viewerOption == 0 : 
               dataset = anaObj[ 'my_output_data' ] #This is e.g, an output dataset of your analysis
               return dataset[ : , :, zselect ]
           elif viewerOption == 1 :
               ...
        """
        return None
    

    @classmethod
    def v_qspectrum( cls, anaObj , x, y , viewerOption=0) :
        """Get from which 3D analysis spectra in x/y should be extracted for presentation in the OMSI viewer
        
           Developer Note: h5py currently supports only a single index list. If the user provides an index-list for both
                           x and y, then we need to construct the proper merged list and load the data manually, or if
                           the data is small enough, one can load the full data into a numpy array which supports 
                           mulitple lists in the selection. 
        
           :param anaObj: The omsi_file_analysis object for which slicing should be performed 
           :param x: x selection string
           :param y: y selection string
           :param viewerOption: If multiple default viewer behaviors are available for a given analysis then this option is used to switch between them.
           
           :returns: The following two elemnts are expected to be returned by this function :
           
                1) 1D, 2D or 3D numpy array of the requested spectra. NOTE: The mass (m/z) axis must be the last axis. For index selection x=1,y=1 a 1D array is usually expected. For indexList selections x=[0]&y=[1] usually a 2D array is expected. For ragne selections x=0:1&y=1:2 we one usually expects a 3D arrya.
                2) None in case that the spectra axis returned by v_qmz are valid for the returned spectrum. Otherwise, return a 1D numpy array with the m/z values for the spectrum (i.e., if custom m/z values are needed for interpretation of the returned spectrum).This may be needed, e.g., in cases where a per-spectrum peak analysis is performed and the peaks for each spectrum appear at different m/z values. 
        """
        
        #Convert the x,y selection to a python selection
        from omsi.shared.omsi_data_selection import selection_string_to_object
        xselect = selection_string_to_object(x) #Convert the selection string to a python selection
        yselect = selection_string_to_object(y) #Convert the selection string to a python selection

        """EDIT_ME Specify the number of custom viewerOptions you are going to provide for qslice"""
        numCustomViewerOptions = 0
        #Expose the qslice viewer functionality of any data dependencies
        if viewerOption >= numCustomViewerOptions :
            return super(omsi_cx,cls).v_qspectrum( anaObj , x , y, viewerOption=numCustomViewerOptions)
        
        """EDIT_ME
        
           Define your custom qspectrum viewer options. Here you need to handle all the different
           behaviors that are custom to your analysis. Note, this function is expected to return
           two object: i) The data for the spectrum and ii) the m/z axis information for the spectrum
           or None, in case that the m/z data is identical to what the v_qmz function returns.
           Below a simple example.
                   
           if viewerOption == 0 : 
               dataset = anaObj[ 'my_output_data' ] #This is e.g, an output dataset of your analysis
               data = dataset[ xselect , yselect, : ]
               return data, None
           elif viewerOption == 1 :
               ...
        """
        return None, None
        
        
    @classmethod
    def v_qmz(cls, anaObj, qslice_viewerOption=0, qspectrum_viewerOption=0) :
        """ Get the mz axes for the analysis
        
            :param anaObj: The omsi_file_analysis object for which slicing should be performed
            :param qslice_viewerOption: If multiple default viewer behaviors are available for a given analysis then this option is used to switch between them for the qslice URL pattern.
            :param qspectrum_viewerOption: If multiple default viewer behaviors are available for a given analysis then this option is used to switch between them for the qspectrum URL pattern.
        
            :returns: The following four arrays are returned by the analysis:
            
                - mzSpectra : Array with the static mz values for the spectra.
                - labelSpectra : Lable for the spectral mz axis 
                - mzSlice : Array of the static mz values for the slices or None if identical to the mzSpectra.
                - labelSlice : Lable for the slice mz axis or None if identical to labelSpectra.
        """
        
        """EDIT_ME: Define the number of custom viewer options for qslice and qspectrum."""
        currObjectiveDim = anaObj['objectiveDim'][0]
        if currObjectiveDim == cls.dimension_index['imageDim'] :
            numCustomSliceViewerOptions = 1
        else:
            numCustomSliceViewerOptions = 2
        
        numCustomSpectrumViewerOptions = 0 
        
        #Compute the output
        mzSpectra =  None
        labelSpectra = None
        mzSlice = None
        labelSlice = None
        #Both viewerOptions point to a data dependency
        if qspectrum_viewerOption >= numCustomSpectrumViewerOptions and qslice_viewerOption>=numCustomSliceViewerOptions :
            """EDIT_ME Replace the omsi_cx class name with your class name"""
            print 'HERE 1'
            mzSpectra, labelSpectra, mzSlice, labelSlice = \
                super(omsi_cx,cls).v_qmz( anaObj, \
                    qslice_viewerOption=qslice_viewerOption-numCustomSliceViewerOptions , \
                    qspectrum_viewerOption=qspectrum_viewerOption-numCustomSpectrumViewerOptions)

        #Implement the qmz pattern for all the custom qslice and qspectrum viewer options.
        if qslice_viewerOption == 0 and currObjectiveDim == cls.dimension_index['imageDim'] :
            mzSpectra, labelSpectra, mzSlice, labelSlice = \
                super(omsi_cx,cls).v_qmz( anaObj, \
                    qslice_viewerOption=0 , \
                    qspectrum_viewerOption=qspectrum_viewerOption-numCustomSpectrumViewerOptions)
            labelSlice = 'Informative Images'
            mzSlice = np.arange(anaObj['infIndices'].shape[0])
    
        if ( qslice_viewerOption == 0 or qslice_viewerOption == 1) and currObjectiveDim == cls.dimension_index['pixelDim'] :
            mzSpectra, labelSpectra, mzSlice, labelSlice = \
                super(omsi_cx,cls).v_qmz( anaObj, \
                    qslice_viewerOption=0 , \
                    qspectrum_viewerOption=qspectrum_viewerOption-numCustomSpectrumViewerOptions)
            if qslice_viewerOption == 0 :
                labelSlice = 'Pixel Leverage Scores'
                mzSlice = np.arange(1)
            elif qslice_viewerOption == 1 :
                labelSlice = 'Pixel Rank'
                mzSlice = np.arange(1)
            
        return mzSpectra, labelSpectra, mzSlice, labelSlice
        
    @classmethod
    def v_qspectrum_viewerOptions(cls , anaObj ) :
        """Get a list of strings describing the different default viewer options for the analysis for qspectrum. 
           The default implementation tries to take care of handling the spectra retrieval for all the depencies
           but can naturally not decide how the qspectrum should be handled by a derived class. However, this
           implementation is often called at the end of custom implementations to also allow access to data from
           other dependencies.
        
            :param anaObj: The omsi_file_analysis object for which slicing should be performed.  For most cases this is not needed here as the support for slice operations is usually a static decission based on the class type, however, in some cases additional checks may be needed (e.g., ensure that the required data is available).
        
            :returns: List of strings indicating the different available viewer options. The list should be empty if the analysis does not support qspectrum requests (i.e., v_qspectrum(...) is not available).
        """
        
        """EDIT_ME Define a list of custom viewerOptions are supported. E.g:
           
           customOptions = ['Peak cube']
        """
        customOptions = []
        dependentOptions = super(omsi_cx ,cls).v_qspectrum_viewerOptions(anaObj)
        re = customOptions + dependentOptions 
        return re

    @classmethod
    def v_qslice_viewerOptions(cls , anaObj ) :
        """Get a list of strings describing the different default viewer options for the analysis for qslice.
           The default implementation tries to take care of handling the spectra retrieval for all the depencies
           but can naturally not decide how the qspectrum should be handled by a derived class. However, this
           implementation is often called at the end of custom implementations to also allow access to data from
           other dependencies.
        
            :param anaObj: The omsi_file_analysis object for which slicing should be performed.  For most cases this is not needed here as the support for slice operations is usually a static decission based on the class type, however, in some cases additional checks may be needed (e.g., ensure that the required data is available).
        
            :returns: List of strings indicating the different available viewer options. The list should be empty if the analysis does not support qslice requests (i.e., v_qslice(...) is not available).
        """
    
        #Define a list of custom viewerOptions are supported. 
        if anaObj['objectiveDim'][0] == cls.dimension_index['imageDim']:
            customOptions = ['Informative Images']
        else:
            customOptions = ['Pixel Leverage Scores', 'Pixel Rank']
                
        dependentOptions = super(omsi_cx ,cls).v_qslice_viewerOptions(anaObj)
        re = customOptions + dependentOptions 
        return re



############################################################
#  3) Making your analysis self-sufficient   (Recommended) #
############################################################

def main(argv=None):
    """EDIT_ME : Optional
    
       Implement this function to enable a user to use your module also as a stand-alone script.
       Remember, you should always call execute(...) to run your analysis and NOT execute_analysis(...)
       
    """
    #Get the input arguments
    import sys
    from sys import argv,exit
    if argv is None:
        argv = sys.argv

   
if __name__ == "__main__":
    main()


"""Test script:
    
from omsi.dataformat.omsi_file import *
from omsi.analysis.multivariate_stats.omsi_cx import *
inputFile = 'test_cx.h5'
f = omsi_file( inputFile , 'a' )
e = f.get_exp(0)
a = e.get_analysis(0)
d = a['peak_cube']
ocxi = omsi_cx(nameKey='testCX_Images')
ocxi.execute( msidata=d , rank=10, objectiveDim=omsi_cx.dimension_index['imageDim'] )
ocxp = omsi_cx(nameKey='testCX_Pixel')
ocxp.execute( msidata=d , rank=10, objectiveDim=omsi_cx.dimension_index['pixelDim'] )
e.create_analysis( ocxi , flushIO=True)
e.create_analysis( ocxp , flushIO=True)
f.close_file()
"""







