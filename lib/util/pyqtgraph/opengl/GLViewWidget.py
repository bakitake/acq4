from pyqtgraph.Qt import QtCore, QtGui, QtOpenGL
from OpenGL.GL import *
import numpy as np

Vector = QtGui.QVector3D

class GLViewWidget(QtOpenGL.QGLWidget):
    """
    Basic widget for displaying 3D data
        - Rotation/scale controls
        - Axis/grid display
        - Export options

    """
    def __init__(self, parent=None):
        QtOpenGL.QGLWidget.__init__(self, parent)
        self.opts = {
            'center': Vector(0,0,0),  ## will always appear at the center of the widget
            'distance': 10.0,         ## distance of camera from center
            'fov':  60,               ## horizontal field of view in degrees
            'elevation':  30,         ## camera's angle of elevation in degrees
            'azimuth': 45,            ## camera's azimuthal angle in degrees 
                                      ## (rotation around z-axis 0 points along x-axis)
        }
        self.items = []
        self.noRepeatKeys = [QtCore.Qt.Key_Right, QtCore.Qt.Key_Left, QtCore.Qt.Key_Up, QtCore.Qt.Key_Down, QtCore.Qt.Key_PageUp, QtCore.Qt.Key_PageDown]
        self.keysPressed = {}
        self.keyTimer = QtCore.QTimer()
        self.keyTimer.timeout.connect(self.evalKeyState)

    def addItem(self, item):
        self.items.append(item)
        if hasattr(item, 'initializeGL'):
            self.makeCurrent()
            item.initializeGL()
        item._setView(self)
        #print "set view", item, self, item.view()
        self.updateGL()
        
    def removeItem(self, item):
        self.items.remove(item)
        item._setView(None)
        self.updateGL()
        
        
    def initializeGL(self):
        glClearColor(0.0, 0.0, 0.0, 0.0)
        self.resizeGL(self.width(), self.height())
        
    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        #self.updateGL()

    def setProjection(self):
        ## Create the projection matrix
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        w = self.width()
        h = self.height()
        dist = self.opts['distance']
        fov = self.opts['fov']
        
        nearClip = dist * 0.001
        farClip = dist * 1000.
        
        r = nearClip * np.tan(fov * 0.5 * np.pi / 180.)
        t = r * h / w
        glFrustum( -r, r, -t, t, nearClip, farClip)
        
    def setModelview(self):
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glTranslatef( 0.0, 0.0, -self.opts['distance'])
        glRotatef(self.opts['elevation']-90, 1, 0, 0)
        glRotatef(self.opts['azimuth']+90, 0, 0, -1)
        center = self.opts['center']
        glTranslatef(center.x(), center.y(), center.z())
        
        
    def paintGL(self):
        self.setProjection()
        self.setModelview()
        glClear( GL_DEPTH_BUFFER_BIT | GL_COLOR_BUFFER_BIT )
        self.drawItemTree()
        
    def drawItemTree(self, item=None):
        if item is None:
            items = [x for x in self.items if x.parentItem() is None]
        else:
            items = item.childItems()
            items.append(item)
        items.sort(lambda a,b: cmp(a.depthValue(), b.depthValue()))
        for i in items:
            if not i.visible():
                continue
            if i is item:
                try:
                    glPushAttrib(GL_ALL_ATTRIB_BITS)
                    i.paint()
                except:
                    import sys
                    sys.excepthook(*sys.exc_info())
                    print "Error while drawing item", i
                finally:
                    glPopAttrib(GL_ALL_ATTRIB_BITS)
            else:
                glMatrixMode(GL_MODELVIEW)
                glPushMatrix()
                tr = i.transform()
                a = np.array(tr.copyDataTo()).reshape((4,4))
                glMultMatrixf(a.transpose())
                self.drawItemTree(i)
                glMatrixMode(GL_MODELVIEW)
                glPopMatrix()
            
        
    def cameraPosition(self):
        """Return current position of camera based on center, dist, elevation, and azimuth"""
        center = self.opts['center']
        dist = self.opts['distance']
        elev = self.opts['elevation'] * np.pi/180.
        azim = self.opts['azimuth'] * np.pi/180.
        
        pos = Vector(
            center.x() + dist * np.cos(elev) * np.cos(azim),
            center.y() + dist * np.cos(elev) * np.sin(azim),
            center.z() + dist * np.sin(elev)
        )
        
        return pos

    def orbit(self, azim, elev):
        """Orbits the camera around the center position. *azim* and *elev* are given in degrees."""
        self.opts['azimuth'] += azim
        self.opts['elevation'] = np.clip(self.opts['elevation'] + elev, -90, 90)
        self.updateGL()
        
    def pan(self, dx, dy, dz, relative=False):
        """
        Moves the center position while holding the camera in place. 
        
        If relative=True, then the coordinates are interpreted such that x
        if in the global xy plane and points to the right side of the view, y is
        in the global xy plane and orthogonal to x, and z points in the global z
        direction. Distances are scaled roughly such that a value of 1.0 moves
        by one pixel on screen.
        
        """
        if not relative:
            self.opts['center'] += QtGui.QVector3D(dx, dy, dz)
        else:
            cPos = self.cameraPosition()
            cVec = self.opts['center'] - cPos
            dist = cVec.length()  ## distance from camera to center
            xDist = dist * 2. * np.tan(0.5 * self.opts['fov'] * np.pi / 180.)  ## approx. width of view at distance of center point
            xScale = xDist / self.width()
            zVec = QtGui.QVector3D(0,0,1)
            xVec = QtGui.QVector3D.crossProduct(cVec, zVec).normalized()
            yVec = QtGui.QVector3D.crossProduct(xVec, zVec).normalized()
            self.opts['center'] = self.opts['center'] + xVec * xScale * dx + yVec * xScale * dy + zVec * xScale * dz
        self.updateGL()
        
    def mousePressEvent(self, ev):
        self.mousePos = ev.pos()
        
    def mouseMoveEvent(self, ev):
        diff = ev.pos() - self.mousePos
        self.mousePos = ev.pos()
        
        if ev.buttons() == QtCore.Qt.LeftButton:
            self.orbit(-diff.x(), diff.y())
            #print self.opts['azimuth'], self.opts['elevation']
        elif ev.buttons() == QtCore.Qt.MidButton:
            self.pan(diff.x(), diff.y(), 0, relative=True)
        
    def mouseReleaseEvent(self, ev):
        pass
        
    def wheelEvent(self, ev):
        if (ev.modifiers() & QtCore.Qt.ControlModifier):
            self.opts['fov'] *= 0.999**ev.delta()
        else:
            self.opts['distance'] *= 0.999**ev.delta()
        self.updateGL()

    def keyPressEvent(self, ev):
        if ev.key() in self.noRepeatKeys:
            ev.accept()
            if ev.isAutoRepeat():
                return
            self.keysPressed[ev.key()] = 1
            self.evalKeyState()
      
    def keyReleaseEvent(self, ev):
        if ev.key() in self.noRepeatKeys:
            ev.accept()
            if ev.isAutoRepeat():
                return
            try:
                del self.keysPressed[ev.key()]
            except:
                self.keysPressed = {}
            self.evalKeyState()
        
    def evalKeyState(self):
        speed = 2.0
        if len(self.keysPressed) > 0:
            for key in self.keysPressed:
                if key == QtCore.Qt.Key_Right:
                    self.orbit(azim=-speed, elev=0)
                elif key == QtCore.Qt.Key_Left:
                    self.orbit(azim=speed, elev=0)
                elif key == QtCore.Qt.Key_Up:
                    self.orbit(azim=0, elev=-speed)
                elif key == QtCore.Qt.Key_Down:
                    self.orbit(azim=0, elev=speed)
                elif key == QtCore.Qt.Key_PageUp:
                    pass
                elif key == QtCore.Qt.Key_PageDown:
                    pass
                self.keyTimer.start(16)
        else:
            self.keyTimer.stop()

        