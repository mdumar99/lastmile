#include "OpenGLView.h"
#include <GL/glew.h>
#include <GLFW/glfw3.h>
#include <cmath>
#include <iostream>
#include <vector>

static const char* VERT_SRC = R"(
#version 330 core
layout(location=0) in vec2 pos;
uniform vec4 color;
void main() { gl_Position = vec4(pos, 0.0, 1.0); }
)";

static const char* FRAG_SRC = R"(
#version 330 core
uniform vec4 color;
out vec4 FragColor;
void main() { FragColor = color; }
)";

OpenGLView::OpenGLView(int w, int h, const std::string& title)
    : _width(w), _height(h), _title(title) {}

OpenGLView::~OpenGLView() {
    if (_vao) glDeleteVertexArrays(1, &_vao);
    if (_vbo) glDeleteBuffers(1, &_vbo);
    if (_shader_program) glDeleteProgram(_shader_program);
    if (_window) glfwDestroyWindow(_window);
    glfwTerminate();
}

bool OpenGLView::init() {
    if (!glfwInit()) { std::cerr<<"[GL] GLFW init failed\n"; return false; }
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
    _window = glfwCreateWindow(_width, _height,
                               _title.c_str(), nullptr, nullptr);
    if (!_window) { std::cerr<<"[GL] Window failed\n"; glfwTerminate(); return false; }
    glfwMakeContextCurrent(_window);
    glfwSwapInterval(1);
    glewExperimental = GL_TRUE;
    if (glewInit()!=GLEW_OK) { std::cerr<<"[GL] GLEW failed\n"; return false; }
    glViewport(0,0,_width,_height);
    if (!compile_shaders()) return false;
    glGenVertexArrays(1,&_vao);
    glGenBuffers(1,&_vbo);
    glBindVertexArray(_vao);
    glBindBuffer(GL_ARRAY_BUFFER,_vbo);
    glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,2*sizeof(float),nullptr);
    glEnableVertexAttribArray(0);
    std::cout<<"[GL] OpenGL "<<glGetString(GL_VERSION)<<"\n";
    return true;
}

bool OpenGLView::compile_shaders() {
    auto compile=[](GLenum t, const char* s)->unsigned int {
        unsigned int sh=glCreateShader(t);
        glShaderSource(sh,1,&s,nullptr);
        glCompileShader(sh);
        int ok; glGetShaderiv(sh,GL_COMPILE_STATUS,&ok);
        if(!ok){char log[512];glGetShaderInfoLog(sh,512,nullptr,log);
                std::cerr<<"[GL] Shader: "<<log<<"\n";}
        return sh;
    };
    unsigned int vs=compile(GL_VERTEX_SHADER,VERT_SRC);
    unsigned int fs=compile(GL_FRAGMENT_SHADER,FRAG_SRC);
    _shader_program=glCreateProgram();
    glAttachShader(_shader_program,vs);
    glAttachShader(_shader_program,fs);
    glLinkProgram(_shader_program);
    glDeleteShader(vs); glDeleteShader(fs);
    int ok; glGetProgramiv(_shader_program,GL_LINK_STATUS,&ok);
    if(!ok){char log[512];glGetProgramInfoLog(_shader_program,512,nullptr,log);
            std::cerr<<"[GL] Link: "<<log<<"\n"; return false;}
    return true;
}

static float to_ndc_x(float x,float mn,float mx){
    return 2.f*(x-mn)/(mx-mn)-1.f;
}
static float to_ndc_y(float y,float mn,float mx){
    return 2.f*(y-mn)/(mx-mn)-1.f;
}

void OpenGLView::draw_circle(float cx,float cy,float r,
                              float red,float grn,float blu,
                              float /*sx*/,float /*sy*/) {
    // r is already in NDC space
    const int N=12;
    std::vector<float> v;
    v.push_back(cx); v.push_back(cy);
    for(int i=0;i<=N;++i){
        float a=2.f*M_PI*i/N;
        v.push_back(cx+r*std::cos(a));
        v.push_back(cy+r*std::sin(a)*(float(_width)/float(_height)));
    }
    glUseProgram(_shader_program);
    glUniform4f(glGetUniformLocation(_shader_program,"color"),
                red,grn,blu,1.f);
    glBindVertexArray(_vao);
    glBindBuffer(GL_ARRAY_BUFFER,_vbo);
    glBufferData(GL_ARRAY_BUFFER,v.size()*sizeof(float),
                 v.data(),GL_DYNAMIC_DRAW);
    glDrawArrays(GL_TRIANGLE_FAN,0,N+2);
}

void OpenGLView::draw_triangle(float cx,float cy,float size,
                                float red,float grn,float blu,
                                float /*sx*/,float /*sy*/) {
    float aspect=float(_width)/float(_height);
    float verts[]={
        cx,           cy+size*1.5f/aspect,
        cx-size,      cy-size/aspect,
        cx+size,      cy-size/aspect,
    };
    glUseProgram(_shader_program);
    glUniform4f(glGetUniformLocation(_shader_program,"color"),
                red,grn,blu,1.f);
    glBindVertexArray(_vao);
    glBindBuffer(GL_ARRAY_BUFFER,_vbo);
    glBufferData(GL_ARRAY_BUFFER,sizeof(verts),verts,GL_DYNAMIC_DRAW);
    glDrawArrays(GL_TRIANGLES,0,3);
}

void OpenGLView::render(const std::vector<ViewRobot>& robots,
                         const std::vector<ViewHub>&   hubs,
                         const ViewStats&,
                         float min_x,float max_x,
                         float min_y,float max_y) {
    glClearColor(0.04f,0.04f,0.08f,1.f);
    glClear(GL_COLOR_BUFFER_BIT);

    // Robot dot size in NDC — fixed pixel size regardless of zoom
    float dot_r = 0.012f;
    float hub_r = 0.022f;

    // Draw hubs — bright yellow triangles
    for(const auto& h:hubs){
        float nx=to_ndc_x(h.x,min_x,max_x);
        float ny=to_ndc_y(h.y,min_y,max_y);
        draw_triangle(nx,ny,hub_r,1.f,0.85f,0.f,1.f,1.f);
    }

    // Draw robots
    for(const auto& r:robots){
        float nx=to_ndc_x(r.x,min_x,max_x);
        float ny=to_ndc_y(r.y,min_y,max_y);

        // Skip if outside NDC range
        if(nx<-1.1f||nx>1.1f||ny<-1.1f||ny>1.1f) continue;

        float red=0,grn=0,blu=0;
        switch(r.status){
            case 0: red=0.4f;grn=0.6f;blu=1.0f;break; // IDLE blue
            case 1: red=0.1f;grn=0.9f;blu=0.2f;break; // DELIVERING green
            case 2: red=1.0f;grn=0.5f;blu=0.1f;break; // RETURNING orange
            case 3: red=1.0f;grn=0.9f;blu=0.0f;break; // CHARGING yellow
            case 4: red=1.0f;grn=0.1f;blu=0.1f;break; // BLOCKED red
        }
        float b=0.5f+0.5f*(r.battery/100.f);
        draw_circle(nx,ny,dot_r,red*b,grn*b,blu*b,1.f,1.f);
    }

    // Draw a white cross at world centre for reference
    float cx=to_ndc_x(0.f,min_x,max_x);
    float cy=to_ndc_y(0.f,min_y,max_y);
    float cross[]={cx-0.02f,cy, cx+0.02f,cy,
                   cx,cy-0.02f, cx,cy+0.02f};
    glUseProgram(_shader_program);
    glUniform4f(glGetUniformLocation(_shader_program,"color"),
                0.5f,0.5f,0.5f,1.f);
    glBindVertexArray(_vao);
    glBindBuffer(GL_ARRAY_BUFFER,_vbo);
    glBufferData(GL_ARRAY_BUFFER,sizeof(cross),cross,GL_DYNAMIC_DRAW);
    glDrawArrays(GL_LINES,0,4);

    glfwSwapBuffers(_window);
}

bool OpenGLView::should_close() const {
    return glfwWindowShouldClose(_window);
}

void OpenGLView::poll_events() {
    glfwPollEvents();
}
