#pragma once
#include <string>
#include <vector>
#include <functional>

// Forward declare to avoid GL headers in main headers
struct GLFWwindow;

struct ViewRobot {
    float x, y;
    float battery;
    int   status;  // 0=idle 1=delivering 2=returning 3=charging 4=blocked
};

struct ViewHub {
    float x, y;
    int   queue;
};

struct ViewStats {
    int    deliveries;
    int    recharges;
    int    jams;
    int    fails;
    double energy_kwh;
    int    events_processed;
    double sim_time;
};

class OpenGLView {
public:
    OpenGLView(int width=1280, int height=720,
               const std::string& title="Last-Mile — Engineering View");
    ~OpenGLView();

    bool init();
    bool should_close() const;

    // Call each frame with current simulation state
    void render(const std::vector<ViewRobot>& robots,
                const std::vector<ViewHub>&   hubs,
                const ViewStats&              stats,
                float world_min_x, float world_max_x,
                float world_min_y, float world_max_y);

    void poll_events();

private:
    int         _width, _height;
    std::string _title;
    GLFWwindow* _window{nullptr};

    unsigned int _shader_program{0};
    unsigned int _vao{0}, _vbo{0};

    bool compile_shaders();
    void draw_circle(float cx, float cy, float r,
                     float red, float green, float blue,
                     float scale_x, float scale_y);
    void draw_triangle(float cx, float cy, float size,
                       float red, float green, float blue,
                       float scale_x, float scale_y);
    void draw_text_overlay(const ViewStats& stats);
};
